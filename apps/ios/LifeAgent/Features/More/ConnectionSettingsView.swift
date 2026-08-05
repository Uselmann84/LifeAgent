import SwiftUI

/// Configure which backend the app talks to and hold the device token securely.
/// In production the token is issued during pairing; here it can be entered for
/// development. The token is stored only in the Keychain, never in plaintext.
struct ConnectionSettingsView: View {
    @EnvironmentObject private var appState: AppState

    @State private var urlString = ""
    @State private var environment: BackendEnvironment = .demo
    @State private var name = ""
    @State private var token = ""
    @State private var saveMessage: String?

    var body: some View {
        Form {
            Section("Backend connection") {
                TextField("Name", text: $name)
                TextField("Base URL", text: $urlString)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                Picker("Environment", selection: $environment) {
                    ForEach(BackendEnvironment.allCases) { env in
                        Text(env.displayName).tag(env)
                    }
                }
            }

            Section {
                SecureField("Device token", text: $token)
            } header: {
                Text("Device token")
            } footer: {
                Text("Stored only in the Keychain. In production this is issued by pairing with the Backend Mac.")
            }

            Section {
                Button("Save & connect") { Task { await save() } }
                    .disabled(URL(string: urlString) == nil)
                if let msg = saveMessage {
                    Text(msg).font(.footnote).foregroundStyle(.secondary)
                }
            }

            Section("Pairing") {
                NavigationLink { PairingView() } label: {
                    Label("Pair with Backend Mac", systemImage: "qrcode.viewfinder")
                }
            }
        }
        .navigationTitle("Connection")
        .onAppear(perform: seedFromCurrent)
    }

    private func seedFromCurrent() {
        name = appState.profile.name
        urlString = appState.profile.baseURL.absoluteString
        environment = appState.profile.environment
    }

    private func save() async {
        guard let url = URL(string: urlString) else { return }
        let profile = ConnectionProfile(id: appState.profile.id,
                                        name: name.isEmpty ? "\(environment.displayName) Backend" : name,
                                        baseURL: url, environment: environment)
        if !token.isEmpty {
            KeychainStore.setToken(token, for: profile.id)
            token = ""
        }
        await appState.switchProfile(profile)
        saveMessage = appState.isOffline ? "Saved, but backend is unreachable." : "Connected."
    }
}

#Preview {
    NavigationStack { ConnectionSettingsView().environmentObject(AppState()) }
}
