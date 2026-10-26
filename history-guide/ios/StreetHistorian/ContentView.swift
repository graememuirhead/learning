import MapKit
import SwiftUI

struct ContentView: View {
    @StateObject private var model = GuideViewModel()
    @State private var cameraPosition: MapCameraPosition = .userLocation(followsHeading: true, fallback: .automatic)
    @State private var typedQuestion = ""

    var body: some View {
        VStack(spacing: 0) {
            Map(position: $cameraPosition) {
                UserAnnotation()
            }
            .mapStyle(.standard(pointsOfInterest: .all))
            .mapControls {
                MapUserLocationButton()
                MapCompass()
            }
            .frame(height: 240)

            conversation

            controls
        }
        .onAppear { model.onAppear() }
    }

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    if model.turns.isEmpty {
                        Text("Point your phone at something interesting and ask, \u{201C}What's that building?\u{201D} or \u{201C}What happened on this street?\u{201D}")
                            .foregroundStyle(.secondary)
                            .padding(.top, 24)
                    }
                    ForEach(model.turns) { turn in
                        TurnView(turn: turn).id(turn.id)
                    }
                    if model.phase == .listening && !model.recognizer.transcript.isEmpty {
                        Text(model.recognizer.transcript)
                            .italic()
                            .foregroundStyle(.secondary)
                    }
                    if model.phase == .thinking {
                        ProgressView("Looking into it\u{2026}")
                    }
                    if let error = model.errorMessage {
                        Text(error).foregroundStyle(.red)
                    }
                }
                .padding()
            }
            .onChange(of: model.turns.count) {
                if let last = model.turns.last {
                    withAnimation { proxy.scrollTo(last.id, anchor: .top) }
                }
            }
        }
    }

    private var controls: some View {
        VStack(spacing: 12) {
            Button(action: model.mainButtonTapped) {
                Label(buttonTitle, systemImage: buttonIcon)
                    .font(.title3.bold())
                    .frame(maxWidth: .infinity, minHeight: 56)
            }
            .buttonStyle(.borderedProminent)
            .tint(model.phase == .listening ? .red : .accentColor)
            .disabled(model.phase == .thinking)

            HStack {
                TextField("Or type a question", text: $typedQuestion)
                    .textFieldStyle(.roundedBorder)
                    .submitLabel(.send)
                    .onSubmit(sendTyped)
                if !model.turns.isEmpty {
                    Button("Clear", role: .destructive, action: model.clearConversation)
                }
            }
        }
        .padding()
        .background(.bar)
    }

    private var buttonTitle: String {
        switch model.phase {
        case .idle: "Ask"
        case .listening: "Done"
        case .thinking: "Thinking\u{2026}"
        case .speaking: "Stop"
        }
    }

    private var buttonIcon: String {
        switch model.phase {
        case .idle: "mic.fill"
        case .listening: "paperplane.fill"
        case .thinking: "hourglass"
        case .speaking: "stop.fill"
        }
    }

    private func sendTyped() {
        let question = typedQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty, model.phase == .idle else { return }
        typedQuestion = ""
        Task { await model.ask(question) }
    }
}

private struct TurnView: View {
    let turn: Turn

    var body: some View {
        VStack(alignment: turn.role == .user ? .trailing : .leading, spacing: 6) {
            Text(turn.content)
                .padding(12)
                .background(turn.role == .user ? Color.accentColor.opacity(0.15) : Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 14))

            ForEach(turn.sources, id: \.self) { source in
                if let url = URL(string: source.url) {
                    Link(source.title, destination: url)
                        .font(.caption)
                        .lineLimit(1)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: turn.role == .user ? .trailing : .leading)
    }
}

#Preview {
    ContentView()
}
