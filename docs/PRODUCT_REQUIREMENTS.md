# Product Requirements

## Vision
A private, local-first AI **Life Agent** that behaves like a highly competent personal executive
assistant: it notices, organizes, remembers, prepares, warns, follows up, and verifies — while
keeping the user in control. It answers: *"What do I need to take care of, and what can the agent
take off my plate?"*

## Primary user experience
Open the iPhone app and immediately see: what needs attention today, what is becoming urgent, who
hasn't responded, what the agent discovered, which proposed actions await approval, upcoming
commitments, open cases, recent important emails, missing information, and tasks the agent can
prepare. The system summarizes, prioritizes, groups, and suppresses low-value information rather
than surfacing every notification.

## Functional pillars
1. Email monitoring & assistance (Gmail first; provider-abstracted).
2. Importance & task/deadline detection (hybrid rules + history + LLM + user feedback).
3. Conservative spam handling (never permanent auto-delete initially).
4. Calendar & reminders (EventKit; drafts/approval-gated writes).
5. Personal **cases** with reusable, data-driven workflows.
6. Document capture, understanding, and inbox.
7. Long-term, user-controlled personal memory.
8. Daily briefings + proactive assistance + weekly/monthly reviews.
9. **Follow-up engine** and a dedicated "Waiting For" view.
10. Approval Center with payload-bound approvals.
11. Full, user-readable audit log.

## Non-functional requirements
- **Privacy:** local inference + local data; no external analytics without opt-in.
- **Security:** approval-gated consequential actions; prompt-injection defense; Keychain secrets;
  Face ID; per-device revocation; emergency stop.
- **Reliability:** fail-safe execution; idempotency; no duplicate sends; verified backups.
- **Two-Mac operation:** dev/build on Development Mac; runtime on Backend Mac; system runs without
  the Development Mac after deployment.
- **Extensibility:** provider/tool/workflow abstractions; localization-ready (EN first; DE/RU next).

## Defaults
Single user · one Backend MacBook Pro M3 · one iPhone · US jurisdiction ·
`America/Los_Angeles` · Gmail · Apple Calendar/Reminders · English · local AI on, remote AI off ·
Autonomy Level 1 · no real destructive action in development · Xcode direct-install distribution.

## First-release definition (done when the user can…)
Install via Xcode → pair securely with the Backend Mac → chat with the local agent → see a Today
briefing → connect Gmail read-only → see important emails & extracted tasks → convert an email into
a case → generate a reply draft → approve/reject a low-risk action in Demo Mode → create a
reminder/calendar draft → view "waiting for" → inspect the activity log → review/delete memory →
use the app remotely over the private network. Real email send, calendar writes, and spam-move stay
feature-flagged until tests pass.

## Success metrics (local only, opt-in)
Important tasks discovered, deadlines saved, cases resolved, drafts accepted with little editing,
follow-ups completed, time-to-recognition of important email, urgent false positives, spam false
positives, actions rejected, cases with no next action, overdue waiting items, notifications
dismissed without action, user-reported helpfulness.

## Final principle
The Life Agent does not replace the user's judgment. Success = the user no longer has to mentally
hold every unfinished obligation because the agent reliably maintains the complete picture and
surfaces the right matter at the right time.
