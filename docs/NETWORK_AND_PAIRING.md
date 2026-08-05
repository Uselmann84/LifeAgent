# Network & Pairing

Three devices, a private WireGuard network (Tailscale), and role-separated access.

## Topology
```
iPhone  ─────────────► Backend Mac Pro M3   (iPhone_user role, Life Agent API)
                 ▲
Development Mac ─┘  (deploy_admin role, deployment/admin only)
```
- HTTPS even over the private network.
- The backend does **not** trust a device merely for being on the same LAN — every request needs a
  valid paired credential.
- Deployment access (Development Mac) and iPhone API access use **separate roles/credentials**.
  Development credentials cannot authorize production agent actions.
- The backend can revoke Development-Mac access independently from iPhone access.

## Tailscale
- Each device joins the tailnet with its own identity.
- Restrict the backend's API port to the tailnet (Tailscale ACLs); no public exposure.
- Optional MagicDNS name for a stable backend host, so the iPhone never hard-codes an IP.

## Pairing (iPhone ↔ Backend Mac, independent of Development Mac)
1. On the Backend Mac (owner/admin), start a pairing session: `POST /api/v1/pairing/start` →
   time-limited, single-use `code` + `qr_payload` + `expires_at`.
2. The iPhone scans the QR (or enters the code) and generates its own device keypair.
3. iPhone verifies the backend identity (pinned backend public key in the QR payload).
4. iPhone calls `POST /api/v1/pairing/complete` with `{ code, device_name, public_key, role }`.
5. Backend verifies the code (unexpired, unused), stores the device as a paired client, and returns
   its own public key.
6. The code is marked used and cannot be reused.

The Development Mac may *display or retrieve* a pairing code only while authenticated as
deploy_admin — it is never a permanent authentication dependency for the iPhone.

## OAuth callback on a private network
Gmail OAuth is completed on/associated with the Backend Mac. Because the backend is on the tailnet:
- Use a loopback/redirect URI reachable from the Backend Mac's browser, or a Tailscale hostname
  registered as an authorized redirect URI in the Google Cloud console.
- The iPhone initiates "connect Gmail" → backend creates the OAuth session → user authorizes →
  provider result returns to the **backend** flow → backend stores the encrypted refresh token in
  the Keychain → iPhone receives **connection status only** (never the token).

## Certificate/key pinning
The iPhone pins the backend's public key captured during pairing. A key change (e.g. reinstall)
requires re-pairing, preventing silent man-in-the-middle substitution.

## Revocation
`POST /api/v1/pairing/revoke/{device_id}` (owner) immediately invalidates a device's credential —
used for a lost iPhone or a decommissioned Development Mac.
