# Workmode Public working discipline

- Every code, behavior, tool, configuration, packaging, or UI change in this
  project must update the root `README.md` and the relevant document under
  `docs/` in the same change.
- Documentation updates must describe the actual shipped behavior; do not
  document an intended capability before its implementation and verification.
- Preserve user projects, sessions, JSONL history, memory, and local data.
- Any durable product object that users or AI can create must ship with an
  equally discoverable way to modify and delete it. Design the whole CRUD
  lifecycle together instead of adding create-only features. Deletion should
  be recoverable by default and must account for references, derived files,
  indexes, and active UI state. Deliberately immutable audit/history records
  are the exception and must have explicit retention semantics rather than
  masquerading as ordinary editable objects.
- Add or update regression tests before changing behavior, then run the
  relevant backend, frontend, and packaging checks.

## User guidance standard

- Write every user-facing guide for a complete beginner. Do not assume the
  user already knows the vendor, account, prerequisite, console, credential,
  billing model, or where a setting is located.
- A setup guide must say where to go, what to click, what to choose or enter,
  what success looks like, and how to resume or replay the guide. Include
  direct official links when an external service is involved.
- Call out region constraints, one-time secrets, possible charges, free-quota
  limits, and the safest cost-control option. Verify unstable vendor steps
  against current official documentation before changing the guide.
- Keep guide progress outside project and domain data. A guide must not create
  a project, session, history record, or tool output merely because it was
  viewed or completed.
