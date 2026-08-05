# Life Agent — iOS App (Phase 1 SwiftUI shell)

A native SwiftUI client for the Life Agent backend. This Phase 1 shell implements
the five-tab structure, the agent response contract, a payload-bound Approval
Center, a backend connection profile, and a persistent environment banner.

> **Two-Mac model.** This app is developed and built **only on the Development
> MacBook** (Xcode). It talks to the backend running on the **Backend MacBook
> Pro M3** over the private Tailscale network. See
> [../../docs/DEVELOPMENT_ENVIRONMENT.md](../../docs/DEVELOPMENT_ENVIRONMENT.md)
> and [../../docs/NETWORK_AND_PAIRING.md](../../docs/NETWORK_AND_PAIRING.md).

## What's implemented

- **Today** — briefing with top priorities, deadlines, important email, suggested actions.
- **Agent** — chat that renders the explicit response contract: *Found / Recommends /
  Prepared / Requires approval / Completed / Could not verify* plus security warnings.
  No hidden chain-of-thought — only a concise user-facing rationale.
- **Cases** — filterable list (Open / Waiting / At-risk / Resolved) with detail.
- **Inbox** — important email surfaced for triage.
- **More** — Approval Center, Activity log, Memory, and Backend connection settings.
- **Approval Center** — cards show exact external effect, risk, target, and full
  changed data. Approval is bound to the exact `payload_hash`; if the backend's
  payload changes the approval is invalidated. High-risk (Level-4) actions require
  Face ID before approving.
- **Environment banner** — always visible for Demo/Development/Staging backends and
  when offline; hidden in Production.
- **App lock** — locks on background; unlocks with Face ID / device passcode.
- **Offline fallback** — when the backend is unreachable, views show cached/mock data
  and the banner switches to an offline state.

Later phases add EventKit, Share Extension, Widgets, App Intents, and camera-based
QR pairing (see [../../docs/IOS_UX_SPEC.md](../../docs/IOS_UX_SPEC.md)).

## Source layout

```
apps/ios/
├── Config/
│   ├── Base.xcconfig          # shared, no secrets
│   ├── Debug.xcconfig         # localhost, Demo
│   ├── Internal.xcconfig      # Backend Mac (Tailnet), Development
│   └── Release.xcconfig       # Backend Mac (Tailnet), Production
└── LifeAgent/
    ├── Info.plist             # injects backend URL + environment from xcconfig
    ├── App/                   # @main app, root tabs, state, app lock
    ├── Models/                # Codable models mirroring the backend contract
    ├── Networking/            # BackendClient, ConnectionProfile, Keychain
    ├── Shared/                # EnvironmentBanner, ApprovalCard, Loadable
    ├── Support/               # MockData (previews + offline fallback)
    └── Features/              # Today, Agent, Cases, Inbox, More
```

## Creating the Xcode project

The repo ships source, not a checked-in `.xcodeproj` (which is noisy to review).
Create the project once, then add these files:

1. In Xcode: **File ▸ New ▸ Project… ▸ iOS App**. Name it `LifeAgent`,
   interface **SwiftUI**, language **Swift**. Save it under `apps/ios/`.
2. Delete the auto-generated `ContentView.swift` and the generated app entry file.
3. **Add Files to "LifeAgent"…** and add the entire `LifeAgent/` source folder
   (create groups from folders). Ensure all `.swift` files are in the app target.
4. Use the provided `LifeAgent/Info.plist` as the target's Info.plist
   (Target ▸ Build Settings ▸ *Info.plist File*).
5. Wire the build configurations to the xcconfig files:
   **Project ▸ Info ▸ Configurations** →
   - `Debug`   → `Config/Debug.xcconfig`
   - `Release` → `Config/Release.xcconfig`
   - Add a new configuration `Internal` (duplicate Release) →
     `Config/Internal.xcconfig`.
6. Add the **LocalAuthentication** framework (auto-linked via `import`).
7. For Debug-only localhost HTTP, add a scoped App Transport Security exception in
   the Debug configuration; keep Release on HTTPS.

Build & run on the Simulator (Debug) — it will use the Demo backend at
`http://127.0.0.1:8787` and show mock data when the backend is not running.

## Connecting to a backend

- **Debug/Simulator:** start the backend on this Mac
  (`cd backend && uvicorn app.main:create_app --factory --port 8787`) — the app
  points at `127.0.0.1:8787` in Demo mode.
- **Internal/Release:** set the Backend Mac's Tailnet hostname in the matching
  xcconfig, then pair the device (More ▸ Connection ▸ Pair with Backend Mac). The
  issued device token is stored **only in the Keychain**.

## Security notes

- No secrets in source or xcconfig. The device bearer token lives in the Keychain
  (`KeychainStore`) and is referenced per connection profile.
- Approvals are payload-hash bound end-to-end; the app never fabricates or mutates
  a `payload_hash`.
- App locks on background; sensitive approvals require device authentication.
