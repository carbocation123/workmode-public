# Retired standalone literature frontend shell

This directory preserves the former port-5176 Vite package and launcher. Its React
source was moved into `frontend/src/literature/` and is now built as the formal
`/literature/` page of Workmode Public. Nothing in this archive is invoked by the
desktop build, FastAPI startup, or release workflow.

The shell was retired to prevent a second API-base configuration, second build
entry, and duplicate frontend source tree from drifting away from the product.
