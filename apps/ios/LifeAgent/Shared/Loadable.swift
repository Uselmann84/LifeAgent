import SwiftUI

/// Generic async loading state for a fetched value.
enum Loadable<Value> {
    case idle
    case loading
    case loaded(Value)
    case failed(String)
}

/// Loads `fetch()`; surfaces live data only. On failure the error is shown —
/// there is no mock/offline fallback.
@MainActor
final class Loader<Value>: ObservableObject {
    @Published var state: Loadable<Value> = .idle

    func load(fetch: @escaping () async throws -> Value) async {
        // Keep showing existing data during a reload; swapping to .loading tears down
        // the List that hosts .refreshable, which cancels the in-flight request (-999).
        if case .loaded = state {} else { state = .loading }
        do {
            state = .loaded(try await fetch())
        } catch {
            if Task.isCancelled { return }
            state = .failed(error.localizedDescription)
        }
    }
}

struct LoadableContent<Value, Content: View>: View {
    let state: Loadable<Value>
    @ViewBuilder let content: (Value) -> Content

    var body: some View {
        switch state {
        case .idle, .loading:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        case let .loaded(value):
            content(value)
        case let .failed(message):
            ContentUnavailableView("Something went wrong", systemImage: "exclamationmark.triangle",
                                   description: Text(message))
        }
    }
}
