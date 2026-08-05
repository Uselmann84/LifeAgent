import SwiftUI
import UIKit

/// Placeholder pairing flow. The Backend Mac generates a time-limited, single-use
/// pairing code (QR) via POST /pairing/start; the phone completes with
/// POST /pairing/complete. Camera-based QR scanning arrives in a later phase;
/// for now the code can be entered manually.
struct PairingView: View {
    @EnvironmentObject private var appState: AppState
    @State private var code = ""
    @State private var deviceName = UIDevice.current.name
    @State private var status: String?

    var body: some View {
        Form {
            Section {
                Text("On the Backend Mac, run the pairing command to generate a single-use code, then enter it here.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section("Pairing code") {
                TextField("Code", text: $code)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                TextField("Device name", text: $deviceName)
            }
            Section {
                Button("Complete pairing") { Task { await complete() } }
                    .disabled(code.isEmpty)
                if let status { Text(status).font(.footnote).foregroundStyle(.secondary) }
            }
        }
        .navigationTitle("Pair Device")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func complete() async {
        // Phase 1 stub: real implementation posts to /pairing/complete with a
        // generated device key pair and stores the returned token in the Keychain.
        status = "Pairing is completed against the Backend Mac in a later phase."
    }
}

#Preview {
    NavigationStack { PairingView().environmentObject(AppState()) }
}
