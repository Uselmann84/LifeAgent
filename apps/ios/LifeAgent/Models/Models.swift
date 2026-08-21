import Foundation

// MARK: - Health

struct HealthStatus: Codable, Equatable {
    let status: String
    let mode: String
    let environment: String
    let backendVersion: String
    let apiVersion: String

    enum CodingKeys: String, CodingKey {
        case status, mode, environment
        case backendVersion = "backend_version"
        case apiVersion = "api_version"
    }
}

// MARK: - Today briefing

struct TodayBriefing: Codable, Equatable {
    let generatedAt: String
    let topPriorities: [PriorityItem]
    let deadlines: [DeadlineItem]
    let importantEmail: [EmailSummary]
    let suggestedActions: [String]

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case topPriorities = "top_priorities"
        case deadlines
        case importantEmail = "important_email"
        case suggestedActions = "suggested_actions"
    }
}

struct PriorityItem: Codable, Equatable, Identifiable {
    let id: String
    let title: String
    let detail: String?
    let priority: String
    let dueAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title, detail, priority
        case dueAt = "due_at"
    }
}

struct DeadlineItem: Codable, Equatable, Identifiable {
    let id: String
    let title: String
    let dueAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title
        case dueAt = "due_at"
    }
}

struct EmailSummary: Codable, Equatable, Identifiable {
    let id: String
    let sender: String
    let subject: String
    let importance: String?
}

// MARK: - Agent response contract
// Mirrors AgentResponse in the backend: found / recommendations / prepared /
// requires_approval / completed / unverified / security_warnings.

struct AgentResponse: Codable, Equatable {
    let rationale: String
    let found: [String]
    let recommendations: [String]
    let prepared: [String]
    let requiresApproval: [String]
    let completed: [String]
    let unverified: [String]
    let securityWarnings: [String]

    enum CodingKeys: String, CodingKey {
        case found, recommendations, prepared, completed, unverified
        case rationale = "reply"
        case requiresApproval = "requires_approval"
        case securityWarnings = "security_warnings"
    }
}

// MARK: - Approvals

struct ApprovalRequest: Codable, Equatable, Identifiable {
    let id: String
    let actionType: String
    let summary: String
    let externalEffect: String?
    let riskLevel: String
    let target: String?
    let payload: [String: AnyCodable]
    let payloadHash: String
    let status: String
    let expiresAt: String?
    let relatedCaseId: String?

    enum CodingKeys: String, CodingKey {
        case id, target, payload, status
        case summary = "reason"
        case actionType = "action_type"
        case externalEffect = "data_affected"
        case riskLevel = "risk_level"
        case payloadHash = "payload_hash"
        case expiresAt = "expires_at"
        case relatedCaseId = "case_id"
    }

    /// Level-4 (irreversible/external high-risk) actions require device auth.
    var requiresDeviceAuth: Bool { riskLevel.lowercased() == "high" }
}

// MARK: - Cases

struct CaseItem: Codable, Equatable, Identifiable {
    let id: String
    let title: String
    let status: String
    let desiredOutcome: String?
    let nextAction: String?
    let nextFollowupAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title, status
        case desiredOutcome = "desired_outcome"
        case nextAction = "agent_next_action"
        case nextFollowupAt = "next_followup_at"
    }
}

// MARK: - Activity + Memory

struct ActivityEntry: Codable, Equatable, Identifiable {
    let id: String
    let action: String
    let summary: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case action = "planned_action"
        case summary = "reasoning_summary"
        case createdAt = "created_at"
    }
}

struct MemoryItem: Codable, Equatable, Identifiable {
    let id: String
    let content: String
    let category: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, content
        case category = "kind"
        case createdAt = "learned_at"
    }
}

// MARK: - AnyCodable
// Minimal type-erased Codable so approval payloads of arbitrary shape can be
// decoded, displayed, and re-encoded without losing fidelity (payload binding).

struct AnyCodable: Codable, Equatable {
    let value: Any

    init(_ value: Any) { self.value = value }

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { value = NSNull() }
        else if let b = try? c.decode(Bool.self) { value = b }
        else if let i = try? c.decode(Int.self) { value = i }
        else if let d = try? c.decode(Double.self) { value = d }
        else if let s = try? c.decode(String.self) { value = s }
        else if let a = try? c.decode([AnyCodable].self) { value = a.map(\.value) }
        else if let o = try? c.decode([String: AnyCodable].self) {
            value = o.mapValues(\.value)
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch value {
        case is NSNull: try c.encodeNil()
        case let b as Bool: try c.encode(b)
        case let i as Int: try c.encode(i)
        case let d as Double: try c.encode(d)
        case let s as String: try c.encode(s)
        case let a as [Any]: try c.encode(a.map(AnyCodable.init))
        case let o as [String: Any]: try c.encode(o.mapValues(AnyCodable.init))
        default: try c.encodeNil()
        }
    }

    static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        String(describing: lhs.value) == String(describing: rhs.value)
    }

    var displayString: String {
        switch value {
        case let s as String: return s
        case let b as Bool: return b ? "true" : "false"
        default: return String(describing: value)
        }
    }
}
