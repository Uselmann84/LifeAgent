import SwiftUI

/// Bulk inbox cleanup: pick a time span, identify bulk/promotional senders, and request a
/// permanent delete. Deletion is irreversible, so this screen only creates an approval — the
/// user confirms it in the Approval Center before anything is deleted.
struct CleanupView: View {
    @EnvironmentObject private var appState: AppState

    @State private var fromDate = Calendar.current.date(byAdding: .year, value: -2, to: .now) ?? .now
    @State private var toDate = Date.now
    @State private var state: Loadable<[SenderGroup]> = .idle
    @State private var selection: Set<String> = []
    @State private var confirming = false
    @State private var deleting = false
    @State private var alert: CleanupAlert?

    private static let apiDate: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .iso8601)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    var body: some View {
        List {
            Section("Time span") {
                DatePicker("From", selection: $fromDate, in: ...toDate, displayedComponents: .date)
                DatePicker("To", selection: $toDate, in: fromDate...Date.now, displayedComponents: .date)
                Button {
                    Task { await scan() }
                } label: {
                    Label("Identify spam", systemImage: "sparkle.magnifyingglass")
                }
                .disabled(isScanning)
            }

            switch state {
            case .idle:
                Section {
                    Text("Pick a range and tap Identify spam. Senders that look like invoices, orders, or bills are protected and never selected.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            case .loading:
                Section {
                    HStack { Spacer(); ProgressView("Scanning inbox…"); Spacer() }
                        .padding(.vertical, 8)
                }
            case let .failed(message):
                Section {
                    ContentUnavailableView("Couldn't scan", systemImage: "exclamationmark.triangle",
                                           description: Text(message))
                }
            case let .loaded(groups):
                resultsSections(groups)
            }
        }
        .navigationTitle("Email Cleanup")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) { deleteBar }
        .alert(item: $alert) { a in
            Alert(title: Text(a.title), message: Text(a.message), dismissButton: .default(Text("OK")))
        }
    }

    private var isScanning: Bool {
        if case .loading = state { return true }
        return false
    }

    @ViewBuilder
    private func resultsSections(_ groups: [SenderGroup]) -> some View {
        let spam = groups.filter { $0.category == "spam" }
        let ads = groups.filter { $0.category == "advertising" }
        let keep = groups.filter { $0.category == "keep" }

        if groups.isEmpty {
            Section { Text("No senders found in this range.").foregroundStyle(.secondary) }
        }
        if !spam.isEmpty { senderSection("Spam", spam, selectable: true) }
        if !ads.isEmpty { senderSection("Advertising", ads, selectable: true) }
        if !keep.isEmpty { senderSection("Kept — invoices, orders, bills", keep, selectable: false) }
    }

    private func senderSection(_ title: String, _ items: [SenderGroup], selectable: Bool) -> some View {
        Section(title) {
            ForEach(items) { g in senderRow(g, selectable: selectable) }
        }
    }

    private func senderRow(_ g: SenderGroup, selectable: Bool) -> some View {
        Button {
            guard selectable else { return }
            if selection.contains(g.sender) { selection.remove(g.sender) } else { selection.insert(g.sender) }
        } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: icon(for: g, selectable: selectable))
                    .foregroundStyle(selectable && selection.contains(g.sender) ? Color.accentColor : .secondary)
                VStack(alignment: .leading, spacing: 3) {
                    Text(g.senderName.isEmpty ? g.sender : g.senderName).font(.headline)
                    if !g.senderName.isEmpty {
                        Text(g.sender).font(.caption).foregroundStyle(.secondary)
                    }
                    if let subject = g.sampleSubjects.first, !subject.isEmpty {
                        Text(subject).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                    }
                    Text(g.reason).font(.caption2).foregroundStyle(.secondary)
                }
                Spacer()
                Text("\(g.count)").font(.callout.monospacedDigit()).foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
        .disabled(!selectable)
    }

    private func icon(for g: SenderGroup, selectable: Bool) -> String {
        guard selectable else { return "lock.fill" }
        return selection.contains(g.sender) ? "checkmark.circle.fill" : "circle"
    }

    @ViewBuilder
    private var deleteBar: some View {
        if !selection.isEmpty {
            Button(role: .destructive) {
                confirming = true
            } label: {
                Label("Request permanent delete (\(selection.count))", systemImage: "trash")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.red)
            .disabled(deleting)
            .padding()
            .background(.bar)
            .confirmationDialog(
                "Permanently delete all mail from \(selection.count) sender(s)? This creates an approval you must confirm; deletion is irreversible.",
                isPresented: $confirming,
                titleVisibility: .visible
            ) {
                Button("Create delete approval", role: .destructive) { Task { await requestDelete() } }
                Button("Cancel", role: .cancel) {}
            }
        }
    }

    private var sinceString: String { Self.apiDate.string(from: fromDate) }

    // IMAP BEFORE is exclusive; add a day so the selected "To" date is included.
    private var beforeString: String {
        let inclusive = Calendar.current.date(byAdding: .day, value: 1, to: toDate) ?? toDate
        return Self.apiDate.string(from: inclusive)
    }

    private func scan() async {
        selection = []
        state = .loading
        do {
            let groups = try await appState.client.scanCleanup(since: sinceString, before: beforeString)
            state = .loaded(groups)
        } catch {
            state = .failed(error.localizedDescription)
        }
    }

    private func requestDelete() async {
        deleting = true
        defer { deleting = false }
        do {
            _ = try await appState.client.requestCleanupDelete(
                senders: Array(selection), since: sinceString, before: beforeString, reason: nil
            )
            selection = []
            alert = CleanupAlert(title: "Approval created",
                                 message: "Open Approval Center to confirm the permanent deletion.")
        } catch {
            alert = CleanupAlert(title: "Couldn't create approval", message: error.localizedDescription)
        }
    }
}

struct CleanupAlert: Identifiable {
    let id = UUID()
    let title: String
    let message: String
}

#Preview {
    NavigationStack { CleanupView().environmentObject(AppState()) }
}
