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

    private static let profileKey = "com.lifeagent.activeProfile"

    init(profile: ConnectionProfile? = nil) {
        // Live mode: reuse the last saved connection so it survives relaunches;
        // only fall back to the compile-time bootstrap on first run.
        let resolved = profile ?? AppState.loadPersistedProfile() ?? .bootstrap
        self.profile = resolved
        self.client = BackendClient(profile: resolved)
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
        AppState.persistProfile(newProfile)
        await refreshHealth()
    }

    private static func loadPersistedProfile() -> ConnectionProfile? {
        guard let data = UserDefaults.standard.data(forKey: profileKey) else { return nil }
        return try? JSONDecoder().decode(ConnectionProfile.self, from: data)
    }

    private static func persistProfile(_ profile: ConnectionProfile) {
        guard let data = try? JSONEncoder().encode(profile) else { return }
        UserDefaults.standard.set(data, forKey: profileKey)
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
