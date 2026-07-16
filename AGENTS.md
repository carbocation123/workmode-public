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
