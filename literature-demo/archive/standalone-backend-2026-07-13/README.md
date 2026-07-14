# Retired standalone literature backend

This directory preserves the first literature vertical-slice backend for historical
comparison only. It owned a separate store, session format, chat loop, compactor,
proposal/confirmation workflow and `/api/literature-demo` routes.

It was retired on 2026-07-13 when the literature interface became a specialized
projection of the formal Workmode project/session/tool/context kernel. Nothing in
`backend/app/main.py` imports this archive, and it must not be added back to the
runtime or release build.

The active frontend was later migrated to `frontend/src/literature/` and the former
port-5176 development shell was archived beside this directory. Neither standalone
implementation belongs to the runtime or release build.
