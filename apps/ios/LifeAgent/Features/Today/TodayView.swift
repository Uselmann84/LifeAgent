import SwiftUI

struct TodayView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var loader = Loader<TodayBriefing>()

    var body: some View {
        NavigationStack {
            LoadableContent(state: loader.state) { briefing in
                List {
                    if !briefing.topPriorities.isEmpty {
                        Section("Top priorities") {
                            ForEach(briefing.topPriorities) { item in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        RiskBadge(risk: item.priority)
                                        Text(item.title).font(.headline)
                                    }
                                    if let detail = item.detail {
                                        Text(detail).font(.subheadline).foregroundStyle(.secondary)
                                    }
                                    if let due = item.dueAt {
                                        Label(due, systemImage: "calendar")
                                            .font(.caption).foregroundStyle(.orange)
                                    }
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }

                    if !briefing.deadlines.isEmpty {
                        Section("Deadlines") {
                            ForEach(briefing.deadlines) { d in
                                Label(d.title, systemImage: "flag")
                                    .badge(d.dueAt ?? "")
                            }
                        }
                    }

                    if !briefing.importantEmail.isEmpty {
                        Section("Important email") {
                            ForEach(briefing.importantEmail) { mail in
                                VStack(alignment: .leading) {
                                    Text(mail.subject).font(.subheadline.weight(.semibold))
                                    Text(mail.sender).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }

                    if !briefing.suggestedActions.isEmpty {
                        Section("Suggested actions") {
                            ForEach(briefing.suggestedActions, id: \.self) { action in
                                Label(action, systemImage: "wand.and.stars")
                            }
                        }
                    }
                }
            }
            .navigationTitle("Today")
            .refreshable { await loadToday() }
            .task { await reload() }
        }
    }

    private func reload() async {
        await appState.refreshHealth()
        await loadToday()
    }

    // Kept out of the refreshable path: refreshHealth() mutates published state
    // mid-pull, which rebuilds the List and cancels the in-flight request.
    private func loadToday() async {
        await loader.load(fetch: { try await appState.client.today() })
    }
}

#Preview {
    TodayView().environmentObject(AppState())
}
