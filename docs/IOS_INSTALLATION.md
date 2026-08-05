# iOS Installation

The iPhone app is built on the **Development Mac** with Xcode and installed on the physical iPhone
over a cable. After install, it talks to the **Backend Mac** over Tailscale — no cable needed for
normal use.

## Prerequisites
- Xcode 15+ on the Development Mac.
- An Apple ID (free personal team) or a paid Apple Developer account (recommended — ~1-year signing
  + TestFlight later). See [APPLE_PLATFORM_LIMITATIONS.md](APPLE_PLATFORM_LIMITATIONS.md).
- iPhone with **Developer Mode** enabled (Settings → Privacy & Security → Developer Mode).

## Open & configure
1. Open `apps/ios/LifeAgent` in Xcode (see `apps/ios/README.md` for the project/SPM layout).
2. Select the project → **Signing & Capabilities** → choose your **Team**.
3. Set a unique **Bundle Identifier** (e.g. `com.<you>.lifeagent`).
4. Confirm entitlements (Face ID/`LocalAuthentication`, Keychain; later: Push, App Intents,
   EventKit, Camera for scan).
5. Build configurations map to environments via `.xcconfig`
   (see [ENVIRONMENT_CONFIGURATION.md](ENVIRONMENT_CONFIGURATION.md)):
   `Debug → Development/Demo`, `Internal → selectable staging/production`, `Release → Production`.
   **Endpoints are not hard-coded.**

## Connect the iPhone & run
1. Plug in the iPhone; trust the Development Mac if prompted.
2. Select the device as the run destination.
3. Build & Run (⌘R). Approve any first-launch permission prompts.

## Pair with the Backend Mac
1. On the Backend Mac, start a pairing session (QR) — see
   [NETWORK_AND_PAIRING.md](NETWORK_AND_PAIRING.md).
2. In the app: **More → Integrations → Pair with backend** → scan the QR.
3. The app generates its device keys, verifies the backend, and stores its paired credential in the
   iOS Keychain.
4. A non-production connection shows a persistent **environment banner**.

## Reinstall / update
- Rebuild from Xcode over cable. Pairing persists unless revoked or the backend signing key rotates.
- **Free team:** re-install roughly weekly (signature expiry). **Paid:** ~1 year.
- Later, distribute via **TestFlight** to avoid cable re-installs.

## Signing expiration handling
The app detects an invalid session/credential and prompts to re-pair; if the app itself won't launch
due to signature expiry, re-install from Xcode. This is expected for private development
distribution and is **not** App Store distribution.
