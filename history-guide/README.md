# Street Historian

An iPhone app for walking around a town. Point your phone at something, ask about it out loud,
and hear its history and a few interesting facts.

```
 iPhone app (SwiftUI)                                   Azure Function (Python)        Claude API
 ───────────────────                                    ───────────────────────        ──────────
 Speech → text (on-device)                              POST /api/ask                  claude-opus-5-5
 GPS + compass heading            ── question + ──▶     builds the prompt      ──▶     + web search
 Reverse geocode (street, town)      place context      keeps the API key              (localised to
 Nearby landmarks (MapKit) with   ◀── answer + ───      off the phone          ◀──     the user's town)
   distance + bearing                 sources
 Text → speech
```

## How it works out what you mean

When you ask "what's that building?", the app sends:

- your GPS position and how accurate it is
- the compass direction the phone is pointing
- the street address and town (reverse geocoding)
- up to 20 named places within 250 m (MapKit points of interest), each with its distance and
  compass bearing from you

Claude matches the place whose bearing is closest to your heading, checks facts with web search
(localised to your town), and writes a short answer meant to be heard rather than read. If it
isn't sure which place you mean, it answers about the likeliest one and names the other. The last
10 exchanges go with each question, so follow-ups like "who built it?" work.

## Layout

| Path | What |
|---|---|
| `ios/StreetHistorian/` | SwiftUI app: `LocationManager` (GPS + heading), `PlaceContext` (geocoding, nearby places, bearings), `SpeechRecognizer`, `Speaker`, `GuideClient`, `GuideViewModel`, `ContentView` |
| `ios/project.yml` | [XcodeGen](https://github.com/yonaskolb/XcodeGen) spec, including the location, microphone and speech permission strings |
| `backend/function_app.py` | `POST /api/ask`: builds the prompt and calls Claude with web search |

## Running it

### 1. Backend

```bash
cd history-guide/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.json.template local.settings.json   # add your ANTHROPIC_API_KEY
func start                                             # Azure Functions Core Tools
```

To test it:

```bash
curl -s localhost:7071/api/ask -H 'Content-Type: application/json' -d '{
  "question": "What is that church?",
  "context": {"latitude": 50.9503, "longitude": 0.7339, "heading": 265,
              "locality": "Rye", "country": "United Kingdom", "country_code": "GB",
              "nearby": [{"name": "St Mary'\''s Church", "distance_m": 35, "bearing": 263}]}
}'
```

To deploy, create a Python Function App (`func azure functionapp publish <name>`), set
`ANTHROPIC_API_KEY` in its app settings, and copy the function key for the app.

### 2. iPhone app (needs a Mac with Xcode 15 or later)

```bash
cd history-guide/ios
brew install xcodegen
cp Config.xcconfig.template Config.xcconfig   # set GUIDE_API_URL and GUIDE_API_KEY
xcodegen
open StreetHistorian.xcodeproj
```

In Xcode, choose your team under Signing & Capabilities and run on your iPhone. The compass and
real GPS only work on a device. In the Simulator you can set a location under Features → Location
and type questions instead of speaking. When testing locally, set `GUIDE_API_URL` to your Mac's
LAN address (for example `http:/$()/192.168.1.20:7071`) and allow HTTP for it, or use a tunnel.

If you don't want XcodeGen, create a new iOS App project in Xcode, drag in the files from
`ios/StreetHistorian/`, add the three usage descriptions and the `GuideAPIURL` / `GuideAPIKey`
keys from `project.yml` to the target's Info tab.

## Notes

- **Cost and speed.** Each question is one Claude request with up to 4 web searches, at
  `effort: "low"` to keep the wait short. Set `CLAUDE_MODEL` in the app settings to use a
  different model.
- **Refusals.** Requests use server-side `fallbacks: "default"`, so if a safety classifier
  declines, Anthropic's recommended fallback model answers instead.
- **The function key ships inside the app.** That's fine for personal use or TestFlight. Before a
  public App Store release, put real user authentication (for example Sign in with Apple) and
  rate limiting in front of `/api/ask`.
