import SwiftUI

/// Generic async loading state for a fetched value, with an offline/mock fallback.
enum Loadable<Value> {
    case idle
    case loading
    case loaded(Value)
    case failed(String)
}

/// Loads `fetch()`; on failure falls back to `mock` and marks the view offline.
@MainActor
final class Loader<Value>: ObservableObject {
    @Published var state: Loadable<Value> = .idle
    @Published var usingFallback = false

    func load(fetch: @escaping () async throws -> Value, fallback: @autoclosure () -> Value) async {
        state = .loading
        do {
            let value = try await fetch()
            usingFallback = false
            state = .loaded(value)
        } catch {
            usingFallback = true
            state = .loaded(fallback())
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
