# Permission & Autonomy Matrix

Autonomy is configurable and defaults to **Level 1 (Prepare)**. The language model may recommend
any action; trusted application code (`backend/security/approval.py`) decides what may execute.

## Autonomy levels

| Level | Name | May do | May NOT do |
|-------|------|--------|------------|
| 0 | Observe only | read authorized info, classify, summarize, identify tasks, suggest | any external modification |
| 1 | Prepare (default) | draft emails/SMS, prepare events/reminders/forms/letters, create internal tasks & cases | apply external changes without approval |
| 2 | Low-risk automation | label email, archive newsletters, create internal reminders, update internal case records, schedule non-sensitive checks | anything sensitive/consequential |
| 3 | Trusted workflow automation | pre-authorized workflows within strict boundaries (known recurring reply, follow-up to existing contact, archive confirmed spam, create event from accepted reservation, cancel subscription below threshold) | anything in Level 4 |
| 4 | Consequential — never fully autonomous | — | ALWAYS requires explicit user approval (see below) |

## Level-4 actions (always explicit approval)
Sensitive/legal communications, filing taxes, submitting government forms, accepting
contracts/terms, purchases, moving money, sharing identity documents, deleting important data,
canceling insurance, admitting liability, agreeing to settlements, communicating with
attorneys/government/insurers/employers on consequential matters, messaging a new/uncertain
recipient, **any irreversible action**.

## Per-tool policy

Each tool declares: `permission`, `approval` requirement, `reversible`, `idempotent`, `min_mode`.

| Tool | Approval | Reversible | Notes |
|------|----------|-----------|-------|
| `search_email`, `get_email_thread`, `classify_email` | none | yes (read) | Level 0+ |
| `draft_email`, `draft_sms`, `create_calendar_event_draft` | none (draft only) | yes | prepares, does not send |
| `create_task`, `update_task`, `create_case`, `link_document_to_case` | none | yes | internal only |
| `store_memory`, `delete_memory` | none (sensitive → confirm) | yes | user-inspectable |
| `schedule_follow_up`, `get_waiting_items` | none | yes | internal |
| `request_email_send_approval` | creates approval | — | binds payload |
| `send_approved_email` | **required** (valid, unexpired, payload-matched) | **no** | Level 3+ only for pre-authorized recurring; else Level 4 |
| `save_approved_calendar_event` | required | partially | write feature-flagged |
| `create_reminder` | required in `controlled_action` | yes | |
| `move_email_to_spam` | **required**, conservative, recoverable | reversible (trash retention) | never permanent auto-delete |

## Approval binding & invalidation
An approval is bound to the exact action payload hash (recipients, subject, body, attachments,
amount, target). If any of these change after approval, the approval is invalidated and the agent
must re-request. Grouped approval is allowed only for low-risk homogeneous actions. Unrelated
actions are never hidden behind one button.

## Configurability
Permissions can be scoped by action type, account, recipient, workflow, and maximum monetary
amount. Financial threshold and per-recipient/per-sender rules are stored in the DB and enforced
deterministically.

## Roles (two-Mac)
| Role | May | May NOT |
|------|-----|---------|
| iPhone User | chat, view data, approve actions, manage tasks/cases, change user-facing rules | deploy code |
| Deployment Admin | deploy, health, restart, sanitized logs, run migrations, rollback | approve agent actions / read personal data |
| Local Backend Owner | init secrets, manage integrations/paired devices/backups, emergency recovery | — |

A deployment credential can never approve emails/messages/financial actions. An iPhone user token
can never deploy backend code.
