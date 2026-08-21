import SwiftUI

/// The Approval Center card. Shows the exact external effect, risk, target, and
/// full changed data. Approval is bound to the exact payload hash; Level-4
/// (high-risk) actions require device auth before approving.
struct ApprovalCard: View {
    let approval: ApprovalRequest
    var onApprove: (ApprovalRequest) -> Void
    var onReject: (ApprovalRequest) -> Void
    var onRevise: (ApprovalRequest, String) -> Void

    @State private var expanded = false
    @State private var showRevise = false
    @State private var reviseText = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                RiskBadge(risk: approval.riskLevel)
                Spacer()
                Text(approval.actionType.replacingOccurrences(of: "_", with: " "))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(approval.summary).font(.headline)

            if let effect = approval.externalEffect {
                Label(effect, systemImage: "arrow.up.forward.app")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            if let target = approval.target {
                Label(target, systemImage: "person.crop.circle")
                    .font(.subheadline)
            }

            DisclosureGroup("Exact changed data", isExpanded: $expanded) {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(approval.payload.sorted(by: { $0.key < $1.key }), id: \.key) { key, value in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(key).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                            Text(value.displayString).font(.callout).textSelection(.enabled)
                        }
                    }
                }
                .padding(.top, 4)
            }
            .font(.subheadline)

            if let expires = approval.expiresAt {
                Label("Expires \(expires)", systemImage: "clock")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            HStack(spacing: 12) {
                Button(role: .destructive) { onReject(approval) } label: {
                    Label("Reject", systemImage: "xmark")
                }
                Button { showRevise = true } label: {
                    Label("Revise", systemImage: "pencil")
                }
                Spacer()
                Button {
                    Task { await approveWithAuthIfNeeded() }
                } label: {
                    Label(approval.requiresDeviceAuth ? "Approve (Face ID)" : "Approve",
                          systemImage: "checkmark")
                }
                .buttonStyle(.borderedProminent)
            }
            .font(.callout)
        }
        .padding()
        .background(.background, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(.quaternary))
        .alert("Ask agent to revise", isPresented: $showRevise) {
            TextField("Instructions", text: $reviseText)
            Button("Send") { onRevise(approval, reviseText); reviseText = "" }
            Button("Cancel", role: .cancel) {}
        }
    }

    private func approveWithAuthIfNeeded() async {
        if approval.requiresDeviceAuth {
            let ok = await AppLock.authenticate(reason: "Approve: \(approval.summary)")
            guard ok else { return }
        }
        onApprove(approval)
    }
}

struct RiskBadge: View {
    let risk: String

    var body: some View {
        Text(risk.uppercased())
            .font(.caption2.weight(.bold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.18), in: Capsule())
            .foregroundStyle(color)
    }

    private var color: Color {
        switch risk.lowercased() {
        case "high": return .red
        case "medium": return .orange
        default: return .green
        }
    }
}
