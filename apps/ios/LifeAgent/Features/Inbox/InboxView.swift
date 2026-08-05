import SwiftUI

/// Inbox: important email + pending classifications. Phase 1 shows the important
/// email surfaced by the Today briefing; full triage arrives in later phases.
struct InboxView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var loader = Loader<TodayBriefing>()

    var body: some View {
        NavigationStack {
            LoadableContent(state: loader.state) { briefing in
                if briefing.importantEmail.isEmpty {
                    ContentUnavailableView("Inbox is clear", systemImage: "tray",
                                           description: Text("No important email needs attention."))
                } else {
                    List(briefing.importantEmail) { mail in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(mail.subject).font(.headline)
                                Spacer()
                                if let importance = mail.importance {
                                    RiskBadge(risk: importance == "high" ? "high" : "low")
                                }
                            }
                            Text(mail.sender).font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("Inbox")
            .refreshable { await reload() }
            .task { await reload() }
        }
    }

    private func reload() async {
        await loader.load(fetch: { try await appState.client.today() }, fallback: MockData.today)
    }
}

#Preview {
    InboxView().environmentObject(AppState())
}
