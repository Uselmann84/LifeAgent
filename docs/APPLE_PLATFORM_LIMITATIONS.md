# Apple Platform Limitations

The private first release installs directly from Xcode over a cable using the user's Apple Developer
signing identity. This is **not** App Store distribution. Known constraints and the compliant
workflows we implement instead:

## Signing & distribution
- **Free personal team:** app signatures expire ~7 days; must re-install. **Paid Apple Developer
  Program ($99/yr):** ~1 year, and enables TestFlight later.
- Direct-cable install requires **Developer Mode** enabled on the iPhone (Settings → Privacy &
  Security → Developer Mode) and trusting the Development Mac.
- Provisioning profiles bind bundle id + entitlements + devices. Adding a device or capability
  requires re-provisioning. Documented in [IOS_INSTALLATION.md](IOS_INSTALLATION.md).

## Messaging
- Apps **cannot** silently send SMS/iMessage from the user's personal number. We use `MessageUI`
  (`MFMessageComposeViewController`) to present a prefilled composer the user must send. Result is
  recorded as user-reported/system-reported. Optional future adapters (Twilio, WhatsApp Business,
  Signal share, Telegram bot) are fully separate from the personal number and require explicit
  configuration.

## Email
- No first-party API to send from the native Mail account silently. Email send happens on the
  **backend** via Gmail API (OAuth), approval-gated. The iPhone never holds the Gmail refresh token.

## Calendar & Reminders
- `EventKit` requires explicit user permission. In Phase 1 we do not modify/delete existing events;
  writes are approval-gated and feature-flagged.

## Background execution
- iOS strictly limits background work. Proactive monitoring runs on the **Backend Mac**, which
  pushes results. The app uses background refresh + push to update; it is not a persistent daemon.

## Push notifications
- APNs requires a paid developer account and proper entitlements. Until configured, we fall back to
  **local notifications** and a **refresh-on-open** model. Payloads avoid sensitive content and can
  hide details on the lock screen. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) §Push.

## Contacts / Photos / Files / Camera
- Each requires explicit permission and is requested only when needed. Share Extension, document
  scan (VisionKit), and Files import arrive in Phase 3.

## Face ID / device auth
- `LocalAuthentication` gates sensitive views and Level-4 approvals; a passcode fallback is
  provided per Apple guidelines.

## CarPlay / Apple Watch
- Watch approval and CarPlay-safe briefings are future extensions, subject to Apple entitlement
  approval; not in the first release.

Where an Apple restriction blocks a requested capability, we implement the closest compliant
workflow and document the limitation here.
