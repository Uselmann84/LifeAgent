# iOS UX Specification

Design language: premium, calm, minimal, native Apple. High information clarity, low visual stress,
generous spacing, strong typography, urgency without excessive red. Dark & light mode, Dynamic Type,
VoiceOver, Reduce Motion, large tap targets. Cases feel like *life matters*, not database rows.

## Navigation — five tabs
1. **Today** — briefing; top-3 priorities; deadlines; upcoming events; suggested actions;
   low-priority collapsed.
2. **Agent** — chat; voice input; attachments; context selection; proposed-action cards;
   streaming responses.
3. **Cases** — Open / Waiting / At-risk / Resolved / Templates.
4. **Inbox** — important email; document inbox; pending classifications; suspected spam;
   new extracted tasks.
5. **More** — Tasks, Calendar, Documents, Contacts, Activity log, Memory, Integrations,
   Permissions, Automation rules, Security, Settings.

## Progressive disclosure
Show the recommended action first; allow details, timeline, documents and audit history to expand.

## Agent response contract
Every action-bearing response visibly separates: **Found / Recommends / Prepared /
Requires approval / Completed / Could not verify.** No hidden chain-of-thought — a concise
user-facing rationale only.

## Approval Center
Each card shows: proposed action, exact external effect, reason, risk level, recipient/target,
full message or changed data, attachments, related case, deadline. Actions: **Approve · Edit ·
Reject · Ask agent to revise.** Approval is bound to the exact payload; if it changes, the card
returns to "needs approval". Grouped approval only for low-risk homogeneous actions.
Face ID / device auth is required before approving Level-4 actions.

## Quick actions (configurable home)
Ask Life Agent · Today · Capture task · Scan document · Forward to agent · Draft email ·
Draft message · Create case · Add reminder · Add calendar event · What am I waiting for? ·
Review approvals · Review suspected spam · Start warranty/insurance/vehicle-registration/tax
workflows.

## App Intents (Siri / Shortcuts / Action Button / Widgets)
"Ask Life Agent", "Capture for Life Agent", "What needs my attention?",
"Scan document into Life Agent", "Create a follow-up".

## Capture & triage
Voice-to-text, Lock-Screen widget, Action Button, Share Sheet, photograph a letter/receipt,
paste a notification. Captured items enter triage: identify → ask only essential questions →
link/create case → extract tasks/deadlines → recommend next action.

## Environment indicator
A persistent, unmistakable banner when connected to **Demo** or **Development** backends so test
data is never confused with production. Production Release builds hide all debug controls.

## Offline
When the backend is unreachable, show cached briefing/tasks/cases/approvals/documents and mark
backend-dependent actions as **queued**. Show backend-offline and version-mismatch states clearly.

## Security UX
App lock on background; Face ID for sensitive views/actions; per-device revocation surfaced in
Security settings; minimal sensitive content on the lock screen (opt-in to show more).

## Phase 1 implemented (SwiftUI shell in `apps/ios`)
Today (mock briefing), Agent (mock chat with action-typed sections), Approvals (payload-bound
approve/reject against the backend), Cases list, More (activity log, memory, backend connection
profile + environment banner). EventKit, Share Extension, Widgets, App Intents arrive in Phase 3.
