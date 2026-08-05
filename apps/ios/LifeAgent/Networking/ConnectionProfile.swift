import Foundation

/// Which backend the app is talking to. Drives the persistent environment
/// banner so demo/development data is never confused with production.
enum BackendEnvironment: String, Codable, CaseIterable, Identifiable {
    case demo
    case development
    case staging
    case production

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .demo: return "Demo"
        case .development: return "Development"
        case .staging: return "Staging"
        case .production: return "Production"
        }
    }

    /// Production hides all debug affordances and shows no banner.
    var showsBanner: Bool { self != .production }
}

/// A saved connection to a backend (Backend Mac in production, localhost in dev).
/// Secrets are NOT stored here in plaintext for production — the device token is
/// held in the Keychain (see KeychainStore) and only referenced by profile id.
struct ConnectionProfile: Codable, Equatable, Identifiable {
    var id: UUID
    var name: String
    var baseURL: URL
    var environment: BackendEnvironment

    init(id: UUID = UUID(), name: String, baseURL: URL, environment: BackendEnvironment) {
        self.id = id
        self.name = name
        self.baseURL = baseURL
        self.environment = environment
    }

    /// API base path per API_SPEC.md.
    var apiRoot: URL { baseURL.appendingPathComponent("api/v1") }

    // Compile-time defaults come from the active .xcconfig via Info.plist.
    static var bootstrap: ConnectionProfile {
        let urlString = Bundle.main.object(forInfoDictionaryKey: "LA_DEFAULT_BACKEND_URL") as? String
            ?? "http://127.0.0.1:8787"
        let envString = Bundle.main.object(forInfoDictionaryKey: "LA_DEFAULT_ENVIRONMENT") as? String
            ?? "demo"
        let url = URL(string: urlString) ?? URL(string: "http://127.0.0.1:8787")!
        let env = BackendEnvironment(rawValue: envString) ?? .demo
        return ConnectionProfile(name: "\(env.displayName) Backend", baseURL: url, environment: env)
    }
}
