import Foundation

struct Turn: Codable, Identifiable {
    enum Role: String, Codable { case user, assistant }

    var id = UUID()
    let role: Role
    let content: String
    var sources: [Source] = []

    private enum CodingKeys: String, CodingKey { case role, content }
}

struct Source: Codable, Hashable {
    let title: String
    let url: String
}

/// Talks to the Street Historian backend (history-guide/backend), which holds the Claude API key.
struct GuideClient {
    enum GuideError: LocalizedError {
        case notConfigured
        case server(String)

        var errorDescription: String? {
            switch self {
            case .notConfigured: "Set GUIDE_API_URL in Config.xcconfig."
            case .server(let message): message
            }
        }
    }

    private struct AskRequest: Encodable {
        let question: String
        let history: [Turn]
        let context: PlaceContext
    }

    private struct AskResponse: Decodable {
        let answer: String?
        let sources: [Source]?
        let error: String?
    }

    private let endpoint: URL?
    private let functionKey: String?

    init(bundle: Bundle = .main) {
        let base = (bundle.object(forInfoDictionaryKey: "GuideAPIURL") as? String)?
            .trimmingCharacters(in: .whitespaces)
        endpoint = base.flatMap { $0.isEmpty ? nil : URL(string: $0)?.appending(path: "api/ask") }
        functionKey = (bundle.object(forInfoDictionaryKey: "GuideAPIKey") as? String).flatMap { $0.isEmpty ? nil : $0 }
    }

    func ask(_ question: String, history: [Turn], context: PlaceContext) async throws -> Turn {
        guard let endpoint else { throw GuideError.notConfigured }

        var request = URLRequest(url: endpoint, timeoutInterval: 90)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let functionKey {
            request.setValue(functionKey, forHTTPHeaderField: "x-functions-key")
        }
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(AskRequest(question: question, history: history, context: context))

        let (data, response) = try await URLSession.shared.data(for: request)
        let decoded = try? JSONDecoder().decode(AskResponse.self, from: data)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0

        guard (200..<300).contains(status), let answer = decoded?.answer else {
            throw GuideError.server(decoded?.error ?? "The guide couldn't answer (HTTP \(status)).")
        }
        return Turn(role: .assistant, content: answer, sources: decoded?.sources ?? [])
    }
}
