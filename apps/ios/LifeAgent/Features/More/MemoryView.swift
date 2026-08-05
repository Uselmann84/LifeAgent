import SwiftUI

struct MemoryView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var loader = Loader<[MemoryItem]>()

    var body: some View {
        LoadableContent(state: loader.state) { items in
            List(items) { item in
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.content).font(.subheadline)
                    if let category = item.category {
                        Text(category.capitalized).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Memory")
        .refreshable { await reload() }
        .task { await reload() }
    }

    private func reload() async {
        await loader.load(fetch: { try await appState.client.memory() }, fallback: MockData.memory)
    }
}

#Preview {
    NavigationStack { MemoryView().environmentObject(AppState()) }
}
