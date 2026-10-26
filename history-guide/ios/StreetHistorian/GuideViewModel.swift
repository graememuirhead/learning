import Combine
import Foundation

/// Runs one conversation turn: listen -> work out where we are -> ask the guide -> speak the answer.
@MainActor
final class GuideViewModel: ObservableObject {
    enum Phase: Equatable {
        case idle, listening, thinking, speaking
    }

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var turns: [Turn] = []
    @Published var errorMessage: String?

    let location = LocationManager()
    let recognizer = SpeechRecognizer()
    let speaker = Speaker()
    private let client = GuideClient()
    private var cancellables: Set<AnyCancellable> = []

    init() {
        // Re-render while words are being recognised.
        recognizer.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
    }

    func onAppear() {
        location.start()
    }

    /// The main button: tap to start listening, tap again to send, tap while talking to stop.
    func mainButtonTapped() {
        switch phase {
        case .idle:
            Task { await startListening() }
        case .listening:
            let question = recognizer.stop()
            phase = .idle
            if !question.isEmpty { Task { await ask(question) } }
        case .speaking:
            speaker.stop()
            phase = .idle
        case .thinking:
            break
        }
    }

    func ask(_ question: String) async {
        guard let here = location.location else {
            errorMessage = "Still finding your location. Make sure Location Services are on for Street Historian."
            return
        }
        errorMessage = nil
        phase = .thinking
        let history = turns
        turns.append(Turn(role: .user, content: question))

        let context = await PlaceContextBuilder.build(location: here, heading: location.heading)
        do {
            let answer = try await client.ask(question, history: history, context: context)
            turns.append(answer)
            phase = .speaking
            speaker.speak(answer.content)
            await waitForSpeechToFinish()
        } catch {
            errorMessage = error.localizedDescription
        }
        if phase != .listening { phase = .idle }
    }

    func clearConversation() {
        speaker.stop()
        turns.removeAll()
        phase = .idle
    }

    private func startListening() async {
        speaker.stop()
        errorMessage = nil
        do {
            phase = .listening
            try await recognizer.start()
        } catch {
            phase = .idle
            errorMessage = error.localizedDescription
        }
    }

    private func waitForSpeechToFinish() async {
        while speaker.isSpeaking && phase == .speaking {
            try? await Task.sleep(for: .milliseconds(200))
        }
    }
}
