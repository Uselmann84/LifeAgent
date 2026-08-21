import SwiftUI

struct MoreView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        NavigationStack {
            List {
                Section("Review") {
                    NavigationLink { ApprovalsView() } label: {
                        Label("Approval Center", systemImage: "checkmark.shield")
                    }
                    NavigationLink { ActivityView() } label: {
                        Label("Activity log", systemImage: "list.bullet.rectangle")
                    }
                    NavigationLink { MemoryView() } label: {
                        Label("Memory", systemImage: "brain")
                    }
                }

                Section("Inbox") {
                    NavigationLink { CleanupView() } label: {
                        Label("Email cleanup", systemImage: "trash.slash")
                    }
                }

                Section("Backend") {
                    NavigationLink { ConnectionSettingsView() } label: {
                        Label("Connection", systemImage: "network")
                    }
                    LabeledContent("Environment", value: appState.environment.displayName)
                    if let health = appState.health {
                        LabeledContent("Backend", value: health.backendVersion)
                        LabeledContent("API", value: health.apiVersion)
                        LabeledContent("Mode", value: health.mode)
                    }
                    LabeledContent("Status", value: appState.isOffline ? "Offline" : "Online")
                }

                Section("Coming later") {
                    ForEach(["Tasks", "Calendar", "Documents", "Contacts",
                             "Integrations", "Permissions", "Automation rules",
                             "Security", "Settings"], id: \.self) { name in
                        Label(name, systemImage: "circle.dashed").foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("More")
        }
    }
}

#Preview {
    MoreView().environmentObject(AppState())
}
