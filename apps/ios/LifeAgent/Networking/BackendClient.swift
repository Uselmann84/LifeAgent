import Foundation

enum BackendError: LocalizedError {
    case notConnected
    case http(Int, String)
    case decoding(String)
    case transport(String)
    case versionMismatch(app: String, backend: String)

    var errorDescription: String? {
        switch self {
        case .notConnected: return "Not paired with a backend."
        case let .http(code, msg): return "Backend error \(code): \(msg)"
        case let .decoding(msg): return "Could not read response: \(msg)"
        case let .transport(msg): return "Cannot reach backend: \(msg)"
        case let .versionMismatch(app, backend):
            return "App (\(app)) and backend (\(backend)) versions are incompatible. Please update."
        }
    }
}

/// Async client for the Life Agent backend. Attaches the device bearer token,
/// targets `/api/v1`, and enforces payload-bound approvals.
actor BackendClient {
    private let profile: ConnectionProfile
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(profile: ConnectionProfile, session: URLSession = .shared) {
        self.profile = profile
        self.session = session
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    // MARK: Requests

    private func makeRequest(_ path: String, method: String = "GET", body: Data? = nil) throws -> URLRequest {
        // Split off any query string; appendingPathComponent would percent-encode "?".
        let parts = path.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)
        let base = profile.apiRoot.appendingPathComponent(String(parts[0]))
        guard var comps = URLComponents(url: base, resolvingAgainstBaseURL: false) else {
            throw BackendError.transport("bad URL")
        }
        if parts.count > 1 { comps.percentEncodedQuery = String(parts[1]) }
        guard let url = comps.url else { throw BackendError.transport("bad URL") }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 15
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token = KeychainStore.token(for: profile.id) {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return req
    }

    private func send<T: Decodable>(_ req: URLRequest, as _: T.Type) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw BackendError.transport(error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else {
            throw BackendError.transport("no HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = String(data: data, encoding: .utf8) ?? ""
            throw BackendError.http(http.statusCode, msg)
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw BackendError.decoding(error.localizedDescription)
        }
    }

    // MARK: Endpoints

    // Backend wraps list responses as {"items": [...]}.
    private struct ItemsEnvelope<T: Decodable>: Decodable { let items: [T] }

    func health() async throws -> HealthStatus {
        try await send(makeRequest("health"), as: HealthStatus.self)
    }

    func today() async throws -> TodayBriefing {
        try await send(makeRequest("today"), as: TodayBriefing.self)
    }

    func chat(message: String, context: [String]? = nil) async throws -> AgentResponse {
        struct Body: Encodable { let message: String; let context: [String]? }
        let body = try encoder.encode(Body(message: message, context: context))
        return try await send(makeRequest("agent/chat", method: "POST", body: body), as: AgentResponse.self)
    }

    func approvals(status: String = "pending") async throws -> [ApprovalRequest] {
        try await send(makeRequest("approvals?status=\(status)"), as: ItemsEnvelope<ApprovalRequest>.self).items
    }

    /// Approve is bound to the exact payload hash. If the backend's current hash
    /// differs, it rejects the approval and the card returns to "needs approval".
    func approve(_ approval: ApprovalRequest) async throws -> ApprovalRequest {
        struct Body: Encodable { let payload_hash: String }
        let body = try encoder.encode(Body(payload_hash: approval.payloadHash))
        return try await send(
            makeRequest("approvals/\(approval.id)/approve", method: "POST", body: body),
            as: ApprovalRequest.self
        )
    }

    func reject(_ approval: ApprovalRequest, reason: String?) async throws -> ApprovalRequest {
        struct Body: Encodable { let reason: String? }
        let body = try encoder.encode(Body(reason: reason))
        return try await send(
            makeRequest("approvals/\(approval.id)/reject", method: "POST", body: body),
            as: ApprovalRequest.self
        )
    }

    func revise(_ approval: ApprovalRequest, instructions: String) async throws -> ApprovalRequest {
        struct Body: Encodable { let instructions: String }
        let body = try encoder.encode(Body(instructions: instructions))
        return try await send(
            makeRequest("approvals/\(approval.id)/revise", method: "POST", body: body),
            as: ApprovalRequest.self
        )
    }

    func cases(status: String? = nil) async throws -> [CaseItem] {
        let path = status.map { "cases?status=\($0)" } ?? "cases"
        return try await send(makeRequest(path), as: ItemsEnvelope<CaseItem>.self).items
    }

    func activity() async throws -> [ActivityEntry] {
        try await send(makeRequest("activity"), as: ItemsEnvelope<ActivityEntry>.self).items
    }

    func memory() async throws -> [MemoryItem] {
        try await send(makeRequest("memory"), as: ItemsEnvelope<MemoryItem>.self).items
    }

    func scanCleanup(since: String, before: String) async throws -> [SenderGroup] {
        struct Body: Encodable { let since: String; let before: String }
        let body = try encoder.encode(Body(since: since, before: before))
        return try await send(
            makeRequest("email/cleanup/scan", method: "POST", body: body),
            as: ItemsEnvelope<SenderGroup>.self
        ).items
    }

    func requestCleanupDelete(
        senders: [String], since: String, before: String, reason: String?
    ) async throws -> CleanupApproval {
        struct Body: Encodable {
            let senders: [String]
            let since: String
            let before: String
            let reason: String?
        }
        let body = try encoder.encode(Body(senders: senders, since: since, before: before, reason: reason))
        return try await send(
            makeRequest("email/cleanup/request-delete", method: "POST", body: body),
            as: CleanupApproval.self
        )
    }
}
