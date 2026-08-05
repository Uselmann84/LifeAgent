import Foundation
import SwiftUI

/// App-wide state: the active backend connection, health/version status, app
/// lock, and a simple offline flag. Kept intentionally small for Phase 1.
@MainActor
final class AppState: ObservableObject {
    @Published var profile: ConnectionProfile
    @Published private(set) var health: HealthStatus?
    @Published private(set) var isOffline = false
    @Published var isLocked = false

    private(set) var client: BackendClient

    init(profile: ConnectionProfile = .bootstrap) {
        self.profile = profile
        self.client = BackendClient(profile: profile)
    }

    var environment: BackendEnvironment {
        // Prefer the live health report; fall back to the configured profile.
        if let env = health.flatMap({ BackendEnvironment(rawValue: $0.environment) }) {
            return env
        }
        return profile.environment
    }

    func switchProfile(_ newProfile: ConnectionProfile) async {
        profile = newProfile
        client = BackendClient(profile: newProfile)
        await refreshHealth()
    }

    func refreshHealth() async {
        do {
            let h = try await client.health()
            health = h
            isOffline = false
            checkVersion(h)
        } catch {
            isOffline = true
        }
    }

    private func checkVersion(_ h: HealthStatus) {
        let appVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
        // Phase 1: only surface API-version mismatches; app follows backend major.
        _ = appVersion
        _ = h.apiVersion
    }
}
