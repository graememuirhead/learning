"""
Street Historian API
Azure Functions v2 (Python)

Keeps the Anthropic API key off the phone: the iOS app sends the spoken
question plus what it knows about where the user is standing, and this
function asks Claude (with web search) for a short, spoken-style answer.

Endpoints
---------
POST   /api/ask
    Body: {
      "question": "What's that church on the corner?",
      "history":  [ { "role": "user" | "assistant", "content": "..." } ],
      "context":  {
        "latitude": 50.95, "longitude": 0.73, "horizontal_accuracy": 8,
        "heading": 270,                       # degrees from true north, optional
        "address": "High Street, Rye", "locality": "Rye",
        "administrative_area": "England", "country": "United Kingdom",
        "country_code": "GB", "time_zone": "Europe/London",
        "nearby": [ { "name": "St Mary's Church", "category": "MKPOICategoryChurch",
                      "distance_m": 40, "bearing": 265 } ]
      }
    }
    Returns: { "answer": "...", "sources": [ { "title": "...", "url": "..." } ] }
"""

from __future__ import annotations

import json
import logging
import os

import anthropic
import azure.functions as func

logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
MAX_HISTORY_TURNS = 10      # earlier turns are dropped once a walk goes on a while
MAX_PAUSE_CONTINUATIONS = 3  # web search turns can pause; resume at most this often

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from app settings

# Kept byte-for-byte stable so it caches; everything per-request goes in the
# user message instead.
SYSTEM_PROMPT = """\
You are a friendly, knowledgeable local historian walking alongside someone \
exploring a town or city. They ask you questions out loud about what they can \
see, and your answer is read aloud to them through their phone.

Each question comes with their GPS position, the compass direction the phone \
is pointing (if known), their street address, and named places nearby with the \
distance and compass bearing from where they stand. Use these to work out what \
they are most likely looking at: a place whose bearing is close to their \
heading and that is close by is the best candidate. If "this" or "that" could \
mean two different places, answer about the likeliest one and briefly name the \
other so they can redirect you.

Use web search to check dates, names and facts before stating them, and prefer \
local history societies, heritage listings and museum sources. Never invent \
dates, architects or anecdotes; if something is uncertain or disputed, say so.

How to answer:
- Write for the ear: plain conversational sentences, no markdown, no lists, no \
URLs, no citation markers. Spell out anything that reads badly aloud.
- Aim for about 100 to 180 words unless they ask for more detail.
- Lead with the direct answer, then the history, then one surprising or \
memorable fact, and if it is natural, point out something nearby worth a look.
- Do not mention coordinates, bearings or that you were given location data.\
"""


def _describe_context(ctx: dict) -> str:
    """Render the phone's location context as plain text for the prompt."""
    lines = []
    lat, lon = ctx.get("latitude"), ctx.get("longitude")
    if lat is not None and lon is not None:
        acc = ctx.get("horizontal_accuracy")
        acc_text = f" (accurate to about {round(acc)} m)" if acc else ""
        lines.append(f"Position: {lat:.6f}, {lon:.6f}{acc_text}")
    if ctx.get("heading") is not None:
        lines.append(f"Phone is pointing towards bearing {round(ctx['heading'])}° (0 = north, 90 = east)")
    address = ", ".join(
        part for part in (
            ctx.get("address"), ctx.get("locality"),
            ctx.get("administrative_area"), ctx.get("country"),
        ) if part
    )
    if address:
        lines.append(f"Address: {address}")

    nearby = ctx.get("nearby") or []
    if nearby:
        lines.append("Named places nearby (distance, bearing from the user):")
        for place in nearby[:20]:
            category = place.get("category") or ""
            category = category.removeprefix("MKPOICategory")
            category_text = f" [{category}]" if category else ""
            lines.append(
                f"- {place.get('name')}{category_text}: "
                f"{round(place.get('distance_m', 0))} m at {round(place.get('bearing', 0))}°"
            )
    return "\n".join(lines) or "Location unknown."


def _web_search_tool(ctx: dict) -> dict:
    tool = {"type": "web_search_20260209", "name": "web_search", "max_uses": 4}
    user_location = {"type": "approximate"}
    if ctx.get("locality"):
        user_location["city"] = ctx["locality"]
    if ctx.get("administrative_area"):
        user_location["region"] = ctx["administrative_area"]
    if ctx.get("country_code"):
        user_location["country"] = ctx["country_code"].upper()
    if ctx.get("time_zone"):
        user_location["timezone"] = ctx["time_zone"]
    if len(user_location) > 1:
        tool["user_location"] = user_location
    return tool


def _build_messages(question: str, history: list, ctx: dict) -> list:
    messages = []
    for turn in history[-MAX_HISTORY_TURNS * 2:]:
        role, content = turn.get("role"), turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    # The API requires the first message to be from the user.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)

    messages.append({
        "role": "user",
        "content": f"<where_i_am>\n{_describe_context(ctx)}\n</where_i_am>\n\n{question}",
    })
    return messages


def _collect_answer(content) -> tuple[str, list[dict]]:
    """Join the text blocks and gather de-duplicated web sources from citations."""
    text_parts, sources, seen = [], [], set()
    for block in content:
        if block.type != "text":
            continue
        text_parts.append(block.text)
        for citation in getattr(block, "citations", None) or []:
            url = getattr(citation, "url", None)
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": getattr(citation, "title", None) or url, "url": url})
    return "".join(text_parts).strip(), sources


def _json(body: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status, mimetype="application/json")


# =========================================================================== #
# POST /api/ask
# =========================================================================== #

@app.route(route="ask", methods=["POST"])
def ask(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return _json({"error": "Request body must be JSON"}, 400)

    question = (body.get("question") or "").strip()
    if not question:
        return _json({"error": "question is required"}, 400)
    ctx = body.get("context") or {}
    history = body.get("history") or []

    messages = _build_messages(question, history, ctx)
    tools = [_web_search_tool(ctx)]
    content = []  # blocks from every response, in case a turn paused part way

    try:
        for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=8000,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                tools=tools,
                # Spoken Q&A: keep latency down.
                output_config={"effort": "low"},
                # If a safety classifier declines, retry server-side on Anthropic's recommended model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            content.extend(response.content)
            if response.stop_reason != "pause_turn":
                break
            # A long web search turn paused; send it back so Claude can carry on.
            messages = messages + [{"role": "assistant", "content": response.content}]
    except anthropic.RateLimitError:
        return _json({"error": "The guide is busy right now. Try again in a moment."}, 429)
    except anthropic.APIStatusError as e:
        logger.exception("Claude API error %s", e.status_code)
        return _json({"error": "The guide couldn't answer that just now."}, 502)
    except anthropic.APIConnectionError:
        logger.exception("Could not reach the Claude API")
        return _json({"error": "The guide couldn't be reached."}, 502)

    if response.stop_reason == "refusal":
        return _json({"answer": "Sorry, I can't help with that one. Try asking about something else you can see.",
                      "sources": []})

    answer, sources = _collect_answer(content)
    if not answer:
        answer = "Sorry, I didn't find anything useful about that. Could you ask another way?"
    return _json({"answer": answer, "sources": sources})
