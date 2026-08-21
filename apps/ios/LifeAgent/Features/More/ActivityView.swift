import SwiftUI

struct ActivityView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var loader = Loader<[ActivityEntry]>()

    var body: some View {
        LoadableContent(state: loader.state) { entries in
            List(entries) { entry in
                VStack(alignment: .leading, spacing: 4) {
                    Text(entry.summary).font(.subheadline)
                    HStack {
                        Text(entry.action.replacingOccurrences(of: "_", with: " "))
                            .font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Text(entry.createdAt).font(.caption2).foregroundStyle(.tertiary)
                    }
                }
            }
        }
        .navigationTitle("Activity")
        .refreshable { await reload() }
        .task { await reload() }
    }

    private func reload() async {
        await loader.load(fetch: { try await appState.client.activity() })
    }
}

#Preview {
    NavigationStack { ActivityView().environmentObject(AppState()) }
}
