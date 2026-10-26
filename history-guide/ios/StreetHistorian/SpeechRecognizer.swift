import AVFoundation
import Speech

/// Turns the user's voice into text while they hold the conversation button.
@MainActor
final class SpeechRecognizer: ObservableObject {
    enum RecognizerError: LocalizedError {
        case notAuthorized, unavailable

        var errorDescription: String? {
            switch self {
            case .notAuthorized: "Microphone or speech recognition permission is off. Turn them on in Settings."
            case .unavailable: "Speech recognition isn't available right now."
            }
        }
    }

    @Published private(set) var transcript = ""
    @Published private(set) var isRecording = false

    private let recognizer = SFSpeechRecognizer(locale: Locale.current) ?? SFSpeechRecognizer()
    private let audioEngine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    func requestAuthorization() async -> Bool {
        let speechAllowed = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
        let micAllowed = await AVAudioApplication.requestRecordPermission()
        return speechAllowed && micAllowed
    }

    func start() async throws {
        guard await requestAuthorization() else { throw RecognizerError.notAuthorized }
        guard let recognizer, recognizer.isAvailable else { throw RecognizerError.unavailable }

        reset()
        transcript = ""

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .measurement, options: [.duckOthers, .defaultToSpeaker])
        try session.setActive(true, options: .notifyOthersOnDeactivation)

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.addsPunctuation = true
        self.request = request

        let input = audioEngine.inputNode
        input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
            request.append(buffer)
        }
        audioEngine.prepare()
        try audioEngine.start()
        isRecording = true

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            let text = result?.bestTranscription.formattedString
            let finished = error != nil || (result?.isFinal ?? false)
            Task { @MainActor in
                guard let self else { return }
                if let text { self.transcript = text }
                if finished { self.reset() }
            }
        }
    }

    /// Stops listening and returns what was heard.
    func stop() -> String {
        request?.endAudio()
        reset()
        return transcript.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func reset() {
        if audioEngine.isRunning {
            audioEngine.stop()
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        task?.cancel()
        task = nil
        request = nil
        isRecording = false
    }
}
