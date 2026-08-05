import LocalAuthentication
import SwiftUI

/// App-lock coordination using device authentication (Face ID / passcode).
enum AppLock {
    static func authenticate(reason: String) async -> Bool {
        let context = LAContext()
        context.localizedFallbackTitle = "Enter Passcode"
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            // No auth available (e.g. Simulator without enrollment): fail open only
            // in non-production so development is possible; production requires auth.
            return false
        }
        return await withCheckedContinuation { cont in
            context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason) { ok, _ in
                cont.resume(returning: ok)
            }
        }
    }

    @MainActor
    static func unlockIfNeeded(_ appState: AppState) async {
        guard appState.isLocked else { return }
        let ok = await authenticate(reason: "Unlock Life Agent")
        if ok { appState.isLocked = false }
    }
}

struct AppLockView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        ZStack {
            Rectangle()
                .fill(.ultraThinMaterial)
                .ignoresSafeArea()
            VStack(spacing: 16) {
                Image(systemName: "lock.shield")
                    .font(.system(size: 44, weight: .semibold))
                    .foregroundStyle(.secondary)
                Text("Life Agent is locked")
                    .font(.headline)
                Button("Unlock") {
                    Task { await AppLock.unlockIfNeeded(appState) }
                }
                .buttonStyle(.borderedProminent)
            }
        }
    }
}
