import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            EnvironmentBanner(environment: appState.environment, isOffline: appState.isOffline)
            TabView {
                TodayView()
                    .tabItem { Label("Today", systemImage: "sun.max") }
                AgentView()
                    .tabItem { Label("Agent", systemImage: "sparkles") }
                CasesView()
                    .tabItem { Label("Cases", systemImage: "folder") }
                InboxView()
                    .tabItem { Label("Inbox", systemImage: "tray") }
                MoreView()
                    .tabItem { Label("More", systemImage: "ellipsis") }
            }
        }
    }
}

#Preview {
    RootView().environmentObject(AppState())
}
