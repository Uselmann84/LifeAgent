import SwiftUI

struct CasesView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var loader = Loader<[CaseItem]>()
    @State private var filter = "all"

    private let filters = ["all", "open", "waiting", "at_risk", "resolved"]

    var body: some View {
        NavigationStack {
            LoadableContent(state: loader.state) { cases in
                List(filtered(cases)) { item in
                    NavigationLink {
                        CaseDetailView(item: item)
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(item.title).font(.headline)
                                Spacer()
                                Text(item.status.capitalized)
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            if let outcome = item.desiredOutcome {
                                Text(outcome).font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Cases")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Picker("Filter", selection: $filter) {
                        ForEach(filters, id: \.self) { Text($0.replacingOccurrences(of: "_", with: " ").capitalized) }
                    }
                }
            }
            .refreshable { await reload() }
            .task { await reload() }
        }
    }

    private func filtered(_ cases: [CaseItem]) -> [CaseItem] {
        filter == "all" ? cases : cases.filter { $0.status == filter }
    }

    private func reload() async {
        await loader.load(fetch: { try await appState.client.cases() }, fallback: MockData.cases)
    }
}

struct CaseDetailView: View {
    let item: CaseItem

    var body: some View {
        List {
            Section("Status") { Text(item.status.capitalized) }
            if let outcome = item.desiredOutcome {
                Section("Desired outcome") { Text(outcome) }
            }
            if let next = item.nextAction {
                Section("Agent next action") { Text(next) }
            }
            if let follow = item.nextFollowupAt {
                Section("Next follow-up") { Label(follow, systemImage: "calendar") }
            }
        }
        .navigationTitle(item.title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    CasesView().environmentObject(AppState())
}
