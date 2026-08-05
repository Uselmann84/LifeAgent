# Threat Model

Scope: a single-user, local-first personal assistant handling highly sensitive personal data
(email, documents, identity references) across a Development MacBook, a Backend MacBook Pro M3,
and an iPhone connected over a private WireGuard network (Tailscale).

## Assets
- Personal email content and OAuth refresh tokens (Backend Mac only).
- Documents and extracted identifiers (SSN-like numbers, VINs, policy/claim numbers).
- Personal memory (preferences, relationships, rules).
- Encryption keys, device-pairing secrets, master key, backup keys.
- Audit log integrity.
- The user's ability to *approve* actions (approval authority itself is an asset).

## Trust boundaries
1. **Untrusted external content ↔ agent** — email bodies, attachments, web pages, documents.
2. **iPhone ↔ Backend API** — over Tailscale; per-device paired credentials.
3. **Development Mac ↔ Backend Mac** — deployment/admin only; separate role & credentials.
4. **Backend ↔ third parties** — Gmail, APNs.
5. **LLM output ↔ tool execution** — model output is untrusted until validated by app code.

## Primary threats & mitigations

| Threat | Mitigation |
|--------|-----------|
| **Prompt injection** from email/doc ("ignore previous instructions", "send your token", "delete all") | Content-trust levels; untrusted text is fenced and never treated as authorization; tool params validated by code; consequential actions require explicit user approval. See `backend/agent/content_trust.py` + tests. |
| **Unauthorized send/delete** | Deterministic approval engine; Level-4 actions never autonomous; payload-bound approvals invalidated if recipients/body/amount/target change. |
| **Recipient spoofing / wrong recipient** | Recipient verification against trusted contacts; new/uncertain recipients force approval; no fuzzy-only selection. |
| **Secret exfiltration** | Secrets in Keychain, not DB/Git/logs; redaction in logs & audit; untrusted content cannot reveal secrets. |
| **Compromised Development Mac** | Dev role cannot approve agent actions or read prod personal data; prod OAuth tokens never leave Backend Mac; backend can revoke dev access independently. |
| **Stolen iPhone** | Face ID / device auth for sensitive views & actions; auto app-lock; per-device revocation; minimal lock-screen notification content. |
| **Network exposure** | No unsecured public API; Tailscale private network; HTTPS even on private net; backend does not trust a device merely for being on the LAN. |
| **Malicious attachment / URL** | Treat attachments as untrusted; malware-risk handling; URL safety checks before surfacing. |
| **Runaway automation** | Autonomy levels; rate limits; emergency stop for all automations; bounded retries. |
| **Data loss** | Verified encrypted backups; restore verification; retention config. |
| **Audit tampering** | Append-only audit entries; no private chain-of-thought stored; export for review. |
| **Replay of pairing code** | Time-limited, single-use pairing codes; per-device crypto identity. |

## Explicitly out of scope (initial phases)
- Multi-user / household sharing.
- Silent sending of iMessage/SMS from the personal number (Apple restriction — see
  [APPLE_PLATFORM_LIMITATIONS.md](APPLE_PLATFORM_LIMITATIONS.md)).
- Permanent automatic email deletion.

## Injection test corpus
Adversarial cases are exercised by `backend/tests/test_content_trust.py`:
instruction override, token exfiltration, mass deletion,
covert forwarding, hidden-in-attachment, and "legal/security notice" disguises. The system must
classify all of these as untrusted and refuse to treat them as authorization.
