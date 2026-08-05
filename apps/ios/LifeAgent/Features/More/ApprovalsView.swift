import SwiftUI

/// Standalone Approval Center: lists all pending, payload-bound approvals and
/// lets the user approve/reject/revise. High-risk actions require device auth.
struct ApprovalsView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var loader = Loader<[ApprovalRequest]>()

    var body: some View {
        LoadableContent(state: loader.state) { approvals in
            if approvals.isEmpty {
                ContentUnavailableView("Nothing to approve", systemImage: "checkmark.shield",
                                       description: Text("No actions are waiting for your approval."))
            } else {
                ScrollView {
                    LazyVStack(spacing: 16) {
                        ForEach(approvals) { approval in
                            ApprovalCard(approval: approval,
                                         onApprove: { resolve($0) { try await appState.client.approve($0) } },
                                         onReject: { resolve($0) { try await appState.client.reject($0, reason: nil) } },
                                         onRevise: { approval, text in
                                             Task { _ = try? await appState.client.revise(approval, instructions: text) }
                                         })
                        }
                    }
                    .padding()
                }
            }
        }
        .navigationTitle("Approval Center")
        .refreshable { await reload() }
        .task { await reload() }
    }

    private func reload() async {
        await loader.load(fetch: { try await appState.client.approvals() },
                          fallback: [MockData.approval])
    }

    private func resolve(_ approval: ApprovalRequest,
                         _ action: @escaping (ApprovalRequest) async throws -> ApprovalRequest) {
        Task {
            _ = try? await action(approval)
            await reload()
        }
    }
}

#Preview {
    NavigationStack { ApprovalsView().environmentObject(AppState()) }
}
