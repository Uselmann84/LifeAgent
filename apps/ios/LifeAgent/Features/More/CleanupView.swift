import SwiftUI

/// Bulk inbox cleanup: pick a time span, identify bulk/promotional senders, and request a
/// permanent delete. The scan runs as a background job on the backend, so it keeps going even if
/// this screen is closed or the app is backgrounded; we poll for progress and partial results and
/// resume automatically on relaunch via a persisted job id. Deletion is irreversible, so this
/// screen only creates an approval the user confirms in the Approval Center.
struct CleanupView: View {
    @EnvironmentObject private var appState: AppState

    @State private var fromDate = Calendar.current.date(byAdding: .year, value: -2, to: .now) ?? .now
    @State private var toDate = Date.now

    @State private var jobId: String?
    @State private var jobStatus = "idle"   // idle | running | done | error
    @State private var phase = ""
    @State private var processed = 0
    @State private var total = 0
    @State private var groups: [SenderGroup] = []
    @State private var errorText: String?

    @State private var selection: Set<String> = []
    @State private var confirming = false
    @State private var deleting = false
    @State private var alert: CleanupAlert?
    @State private var pollTask: Task<Void, Never>?

    // The date range the running job actually used (persisted so delete stays correct on relaunch).
    @AppStorage("cleanup.jobId") private var savedJobId = ""
    @AppStorage("cleanup.since") private var savedSince = ""
    @AppStorage("cleanup.before") private var savedBefore = ""

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
                    .disabled(isRunning)
                DatePicker("To", selection: $toDate, in: fromDate...Date.now, displayedComponents: .date)
                    .disabled(isRunning)
                Button {
                    Task { await startScan() }
                } label: {
                    Label(isRunning ? "Scanning…" : "Identify spam", systemImage: "sparkle.magnifyingglass")
                }
                .disabled(isRunning)
            }

            if isRunning || (jobStatus == "done" && !groups.isEmpty) {
                progressSection
            }

            switch jobStatus {
            case "idle":
                Section {
                    Text("Pick a range and tap Identify spam. The scan runs on the backend and keeps going if you close the app. Senders that look like invoices, orders, or bills are protected and never selected.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            case "error":
                Section {
                    ContentUnavailableView("Couldn't scan", systemImage: "exclamationmark.triangle",
                                           description: Text(errorText ?? "Unknown error"))
                }
            default:
                resultsSections
            }
        }
        .navigationTitle("Email Cleanup")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) { deleteBar }
        .alert(item: $alert) { a in
            Alert(title: Text(a.title), message: Text(a.message), dismissButton: .default(Text("OK")))
        }
        .onAppear { resumeIfNeeded() }
        .onDisappear { pollTask?.cancel() }
    }

    private var isRunning: Bool { jobStatus == "running" }

    private var progressSection: some View {
        Section {
            HStack(spacing: 12) {
                if isRunning { ProgressView() }
                VStack(alignment: .leading, spacing: 2) {
                    Text(progressTitle).font(.subheadline)
                    if total > 0 {
                        ProgressView(value: Double(processed), total: Double(max(total, 1)))
                    }
                }
            }
            .padding(.vertical, 2)
        }
    }

    private var progressTitle: String {
        switch (jobStatus, phase) {
        case ("done", _): return "Done — \(groups.count) senders"
        case (_, "fetching"): return "Reading inbox…"
        default:
            return total > 0 ? "Classifying \(processed)/\(total)…" : "Scanning…"
        }
    }

    @ViewBuilder
    private var resultsSections: some View {
        let spam = groups.filter { $0.category == "spam" }
        let ads = groups.filter { $0.category == "advertising" }
        let keep = groups.filter { $0.category == "keep" }

        if groups.isEmpty && jobStatus == "done" {
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

    private func startScan() async {
        pollTask?.cancel()
        selection = []
        groups = []
        processed = 0
        total = 0
        errorText = nil
        jobStatus = "running"
        phase = "fetching"
        let since = sinceString
        let before = beforeString
        do {
            let id = try await appState.client.startCleanupScan(since: since, before: before)
            jobId = id
            savedJobId = id
            savedSince = since
            savedBefore = before
            startPolling(id)
        } catch {
            jobStatus = "error"
            errorText = error.localizedDescription
        }
    }

    private func resumeIfNeeded() {
        guard jobId == nil, !savedJobId.isEmpty, jobStatus == "idle" else { return }
        jobId = savedJobId
        jobStatus = "running"
        phase = ""
        startPolling(savedJobId)
    }

    private func startPolling(_ id: String) {
        pollTask?.cancel()
        pollTask = Task {
            var failures = 0
            while !Task.isCancelled {
                do {
                    let s = try await appState.client.cleanupScanStatus(jobId: id)
                    failures = 0
                    processed = s.processed
                    total = s.total
                    phase = s.phase
                    groups = s.items
                    jobStatus = s.status
                    if s.status == "done" { return }
                    if s.status == "error" {
                        errorText = s.error ?? "Scan failed"
                        clearSaved()
                        return
                    }
                } catch {
                    failures += 1
                    if failures >= 5 {
                        jobStatus = "error"
                        errorText = error.localizedDescription
                        return
                    }
                }
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }

    private func requestDelete() async {
        deleting = true
        defer { deleting = false }
        let since = savedSince.isEmpty ? sinceString : savedSince
        let before = savedBefore.isEmpty ? beforeString : savedBefore
        do {
            _ = try await appState.client.requestCleanupDelete(
                senders: Array(selection), since: since, before: before, reason: nil
            )
            selection = []
            alert = CleanupAlert(title: "Approval created",
                                 message: "Open Approval Center to confirm the permanent deletion.")
        } catch {
            alert = CleanupAlert(title: "Couldn't create approval", message: error.localizedDescription)
        }
    }

    private func clearSaved() {
        savedJobId = ""
        savedSince = ""
        savedBefore = ""
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
