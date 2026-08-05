# Domain Model

Storage is **domain-first**: explicit entities, not unstructured chat. Implemented in
`backend/core/models.py` (SQLModel). IDs are UUID strings; timestamps are timezone-aware UTC.

## Entities

### Person
`id, name, relationship, emails[], phones[], organization_id?, preferred_channel,
notes, trusted(bool), created_at, updated_at`

### Organization
`id, name, category, website, phones[], account_identifiers[], notes, created_at, updated_at`
Has: contacts (Person), open cases, related documents.

### Task
`id, title, description, status(open|in_progress|waiting|blocked|done|cancelled),
priority(low|normal|high|urgent), due_at?, source, related_email_id?, case_id?,
related_person_id?, related_org_id?, dependencies[], checklist[json], agent_recommendation?,
approval_status, completion_evidence?, created_at, updated_at`

### Case (persistent life matter)
`id, case_type, title, status(open|waiting|at_risk|resolved), desired_outcome, background,
timeline[json], parties[], reference_numbers[json], important_dates[json], missing_information[],
risks[], agent_next_action?, next_followup_at?, resolution_summary?, created_at, updated_at`
Case types: tax, vehicle_registration, warranty, insurance, immigration, school, medical_billing,
home_repair, subscription_cancellation, travel, purchase_return, reimbursement, other.

### Communication
`id, channel(email|sms|call_note|letter|form|in_app), sender, recipients[], sent_at, thread_id?,
summary, intent?, urgency?, task_id?, case_id?, attachments[], follow_up_required(bool),
follow_up_at?, provider_message_id?`

### Document
`id, filename, file_hash, source, doc_type, extracted_text?, summary?, important_dates[json],
parties[], reference_numbers[json], case_id?, sensitivity(low|normal|high|secret),
retention_policy, storage_ref, created_at`

### ApprovalRequest
`id, action_type, reason, data_affected, payload[json], payload_hash, risk_level(low|medium|high|critical),
status(pending|approved|rejected|revise|expired|invalidated), expires_at, approved_by?, approved_at?,
execution_result?, case_id?, created_at`
The `payload_hash` binds the approval; any payload change invalidates it.

### AgentAction (audit)
`id, planned_action, tools_used[], inputs_redacted[json], outputs_redacted[json], reasoning_summary,
approval_id?, success(bool?), reversible(bool), rollback_info?, evidence?, account_affected?,
data_read[], data_changed[], external_confirmation_id?, followup_scheduled_at?, created_at`
Stores a **concise decision summary**, never private chain-of-thought.

### MemoryItem
`id, kind(fact|preference|instruction|routine|relationship|rule|do_not), content, source,
confidence, inferred(bool), sensitivity, learned_at, last_confirmed_at?, expires_at?, case_id?`
User-inspectable, editable, deletable. Sensitive memories flagged; raw secrets never stored here.

### Supporting
- **EmailMessage / EmailThread** (mock + provider-backed): importance category, why-it-matters,
  requested action, deadline, confidence.
- **PairedDevice**: `id, name, role(iphone_user|deploy_admin|owner), public_key, created_at,
  last_seen_at, revoked(bool)`.
- **PairingCode**: `code_hash, role, expires_at, used(bool)`.

## Enumerated model profiles (routing)
`development-fast, development-full, production-fast, production-reasoning, production-embedding,
production-document`. Chosen by task type, never by hard-coded model name.

## Importance categories (email)
`critical, needs_action_today, needs_action_soon, waiting_for_response, informational,
newsletter, promotion, likely_spam, dangerous`.
