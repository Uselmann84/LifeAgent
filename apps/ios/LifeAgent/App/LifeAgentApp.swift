import SwiftUI

@main
struct LifeAgentApp: App {
    @StateObject private var appState = AppState()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .task { await appState.refreshHealth() }
                .overlay {
                    if appState.isLocked {
                        AppLockView()
                    }
                }
        }
        .onChange(of: scenePhase) { _, phase in
            // Lock on background per Security UX; unlock via Face ID on return.
            switch phase {
            case .background: appState.isLocked = true
            case .active: Task { await AppLock.unlockIfNeeded(appState) }
            default: break
            }
        }
    }
}
