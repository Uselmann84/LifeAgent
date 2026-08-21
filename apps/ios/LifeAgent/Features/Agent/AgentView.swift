import SwiftUI

/// Agent chat. Renders the explicit response contract: Found / Recommends /
/// Prepared / Requires approval / Completed / Could not verify — never hidden
/// chain-of-thought, only a concise user-facing rationale.
struct AgentView: View {
    @EnvironmentObject private var appState: AppState
    @State private var input = ""
    @State private var turns: [AgentTurn] = []
    @State private var sending = false

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        ForEach(turns) { turn in
                            AgentTurnView(turn: turn)
                            .id(turn.id)
                        }
                        if sending { ProgressView().padding() }
                    }
                    .padding()
                }
                .onChange(of: turns.count) { _, _ in
                    if let last = turns.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
                }
            }
            .safeAreaInset(edge: .bottom) { composer }
            .navigationTitle("Agent")
        }
    }

    private var composer: some View {
        HStack(spacing: 8) {
            TextField("Ask Life Agent…", text: $input, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...4)
            Button {
                Task { await send() }
            } label: {
                Image(systemName: "arrow.up.circle.fill").font(.title2)
            }
            .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty || sending)
        }
        .padding()
        .background(.bar)
    }

    private func send() async {
        let message = input.trimmingCharacters(in: .whitespaces)
        guard !message.isEmpty else { return }
        turns.append(AgentTurn(role: .user, text: message))
        input = ""
        sending = true
        defer { sending = false }
        do {
            let response = try await appState.client.chat(message: message)
            turns.append(AgentTurn(role: .agent, response: response))
        } catch {
            let failure = AgentResponse(
                rationale: "Couldn't reach the backend: \(error.localizedDescription)",
                found: [], recommendations: [], prepared: [],
                requiresApproval: [], completed: [], unverified: [], securityWarnings: []
            )
            turns.append(AgentTurn(role: .agent, response: failure))
        }
    }
}

struct AgentTurn: Identifiable {
    enum Role { case user, agent }
    let id = UUID()
    let role: Role
    var text: String?
    var response: AgentResponse?

    init(role: Role, text: String) { self.role = role; self.text = text }
    init(role: Role, response: AgentResponse) { self.role = role; self.response = response }
}

struct AgentTurnView: View {
    let turn: AgentTurn

    var body: some View {
        if turn.role == .user {
            HStack {
                Spacer()
                Text(turn.text ?? "")
                    .padding(10)
                    .background(.tint, in: RoundedRectangle(cornerRadius: 14))
                    .foregroundStyle(.white)
            }
        } else if let r = turn.response {
            VStack(alignment: .leading, spacing: 12) {
                Text(r.rationale).font(.body)
                section("Found", r.found, "magnifyingglass", .blue)
                section("Recommends", r.recommendations, "lightbulb", .yellow)
                section("Prepared", r.prepared, "doc.text", .indigo)
                section("Completed", r.completed, "checkmark.seal", .green)
                section("Could not verify", r.unverified, "questionmark.circle", .gray)
                if !r.securityWarnings.isEmpty {
                    section("Security warnings", r.securityWarnings, "exclamationmark.shield", .red)
                }
                section("Requires approval", r.requiresApproval, "hand.raised", .orange)
            }
        }
    }

    @ViewBuilder
    private func section(_ title: String, _ items: [String], _ icon: String, _ color: Color) -> some View {
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Label(title, systemImage: icon)
                    .font(.caption.weight(.bold)).foregroundStyle(color)
                ForEach(items, id: \.self) { Text("• \($0)").font(.subheadline) }
            }
        }
    }
}

#Preview {
    AgentView().environmentObject(AppState())
}
