# Workmode Public Architecture

## Design goal

Workmode Public is a standalone research-work assistant. It intentionally excludes companion/persona modules and starts from a minimal local-first architecture.

## Backend

Backend entry:

```text
backend/app/main.py
```

Main modules:

- `config.py` — environment-based configuration, local data directory, model settings, release env/static path overrides.
- `storage.py` — file-based projects, sessions, messages, and project memory. Registered project roots keep an optional parent relationship; project/session removal is soft-delete metadata and never deletes the user's project directory.
- `context_imports.py` — expands project-local `@relative/path.md` imports.
- `files.py` — project sandbox, text/media preview whitelist, Markdown save path.
- `project_tools.py` — model-callable work tools: project read/write/edit/list_dir/glob/grep/bash/python plus web/state-tool dispatch.
- `web_tools.py` — bounded parallel `web_search` / `web_fetch`, HTML-to-text extraction, redirect validation, response-size limits, and SSRF defenses.
- `work_state.py` — project/global work memory and current plan state; memory index, memory bodies, and plan summary are injected into prompt.
- `session_compactor.py` — manual context compression marker insertion; full JSONL history is preserved.
- `context_window.py` — token-budget history selection; keeps recent legal user/system starts and avoids orphan tool results.
- `prompt.py` — neutral research assistant system prompt and token usage estimate.
- `llm.py` — OpenAI-compatible streaming chat client with project tool-calling loop.
- `routes.py` — `/api/work/*` resources.
  - `POST /api/work/pick-directory` opens a native folder picker for local desktop use.
  - `PATCH/DELETE /api/work/sessions/{id}` rename and archive conversations.
  - `DELETE /api/work/projects/{slug}` archives only the app registration and returns `local_files_deleted=false`.
  - `POST /api/work/sessions/{id}/stop` cancels an active model/tool run.
- `chat_runs.py` — per-session run registry and cancellation tokens used by streaming chat and cancellable command tools.

Runtime data defaults to `%APPDATA%\WorkmodePublic` on Windows and `~/.workmode-public` elsewhere. Set `WORKMODE_PUBLIC_DATA_DIR` to override. The Tauri desktop shell explicitly sets it to `%LOCALAPPDATA%\WorkmodePublic\data`; the legacy portable package sets it to package-local `data/`.

Release startup sets:

- `WORKMODE_ENV_FILE=<package>/config/.env`
- `WORKMODE_STATIC_DIR=<package>/app/frontend-dist`
- `WORKMODE_PUBLIC_DATA_DIR=<package>/data`
- `WORKMODE_APP_VERSION` from `<package>/app/version.json`

## Frontend

Frontend entry:

```text
frontend/src/App.tsx
```

The frontend is a standalone React workspace with an IDE-style shell:

1. 48px activity bar;
2. project/file/session sidebar;
3. chat and context panel;
4. resizable file viewer;
5. bottom status bar.

The project area is a persistent hierarchy rather than a creation-order list. A registered directory nested inside another registered project is displayed below its nearest parent. Conversation rows support rename and soft delete, while the send button changes to a stop action during generation.

The conversation timeline merges `tool_call_start` and `tool_result` events by `tool_call_id` into one compact stateful card. It follows streamed content only while the reader remains near the bottom; manual upward scrolling pauses following and exposes a `Back to latest` control.

It has no dependency on daily mode routing or private persona state.

The visual shell follows the archived `work-mode-v2` IDE layout: ActivityBar, SidePanel, central AI panel, right FileViewPanel, and bottom StatusBar.

The one-click Windows launcher builds `frontend/dist` and lets FastAPI serve the static app. The Vite dev server is only needed for frontend development.

Release packages copy `frontend/dist` to `app/frontend-dist`; target machines do not need Node.js.

## Desktop distribution

The primary distribution is a Tauri 2 Windows application:

```text
desktop/
  package.json
  src-tauri/
    src/
      lib.rs                app, tray, single-instance, backend lifecycle
      backend.rs            dynamic-port launch specification
      paths.rs              installed resources vs user-data paths
      migration.rs          non-destructive legacy import
    capabilities/           narrow updater/dialog/process permissions
    resources/              generated staging area; never contains secrets
scripts/
  build-desktop.ps1         test, stage, sign, bundle, and publish artifacts
```

The shell starts the bundled Python backend on an available loopback port, waits for `/api/health`, then gives the dynamic API base to the frontend. Closing the main window exits the application and terminates the backend process tree. A single-instance guard focuses the existing window. The tray can restore a minimized window or stop and exit. The bundled interpreter runs with `PYTHONDONTWRITEBYTECODE=1`, so runtime caches do not mutate the installation directory or survive uninstall.

Installed resources are immutable application files. User-owned state lives under `%LOCALAPPDATA%\WorkmodePublic`:

```text
WorkmodePublic/
  config/.env
  data/
  logs/
```

Updater artifacts use Tauri's mandatory minisign verification. The updater public key is compiled into the app; the private key and password stay only in the ignored `.release-secrets/` directory. Windows Authenticode signing is a separate release concern and is not provided by the updater signature.

## Legacy portable distribution layout

Source tree:

```text
workmode-public/
  backend/
  frontend/
  scripts/
    one-click-start.ps1      development/source launcher
    build-release.ps1        release package builder
    release/                 scripts copied into release packages
```

Release package:

```text
workmode-public-<version>-win-x64/
  WorkmodePublic.cmd
  StopWorkmodePublic.cmd
  UpdateWorkmodePublic.cmd
  UpgradeExistingWorkmode.cmd
  升级已有版本.cmd
  app/
    backend/
    frontend-dist/
    version.json
  config/
    .env.example
    .env                  created on first launch
  data/                   user data, preserved across updates
  logs/
  runtime/
    python-base/          copied Python base runtime
    backend-venv/         backend dependencies
  backups/                previous app versions after update
```

The updater preserves `config/`, `data/`, `logs/`, and `runtime/`; it replaces only `app/` and refreshes docs/example files when present. This keeps user projects and model credentials stable across application updates.

There are two update paths:

- `升级已有版本.cmd` / `UpgradeExistingWorkmode.cmd`: migration-style update for non-technical users. It runs from the new extracted package, asks the user to choose the old package folder, copies old `config/.env` and `data/` into the new package, then starts the new app. The old folder is untouched and can be deleted after the user verifies the new app.
- `UpdateWorkmodePublic.cmd`: in-place update for advanced users and future manifest-driven updates. It runs inside an existing package folder and replaces only `app/`.

## Context flow

```text
project memory
  ├─ @relative files
  │   └─ context_imports.expand_project_imports_detailed
  └─ work_state memory index + active plan summary
      └─ prompt.build_system_prompt

session JSONL
  └─ session_compactor.messages_visible_to_llm
      └─ prompt._history_to_openai_messages
          └─ context_window.build_context_window
              └─ prompt.build_llm_messages
                  └─ llm.stream_openai_compatible
                      ├─ all required work tool schemas
                      ├─ project_tools.execute_project_tool
                      ├─ work_state.execute_state_tool
                      └─ tool_result back into model loop
```

Only project-local relative imports are accepted. Imported file metadata is returned to the frontend context strip without exposing duplicate file bodies in the UI.

Work memory is fixed-injected with both index and entry bodies. `memory_read` remains available for explicit refresh or exact re-reading of a single entry.

## Context compression and tool history

Session JSONL is the durable archive. It preserves user messages, assistant messages, tool call events, tool result events, and context summary markers. The model view is not the full archive:

1. `messages_visible_to_llm` starts from the latest `<CONTEXT_SUMMARY>` marker when one exists.
2. `prompt._history_to_openai_messages` reconstructs persisted tool call/result UI events into OpenAI-compatible assistant `tool_calls` and `tool` messages.
3. `context_window.build_context_window` subtracts system prompt and tool schema tokens from the configured budget, then loads the newest legal suffix of history.
4. A selected history suffix must start from a user/system message, so the model is not handed an orphan tool result.

Manual compression is exposed as `POST /api/work/sessions/{id}/compact`. It inserts a system marker with an 8-section summary and keeps the original messages before the marker. Repeated compression uses the newest marker as the next continuation boundary.

## Project tool events

When the model calls a project tool, the backend emits SSE events:

- `tool_call_start` — tool name and JSON input;
- `tool_result` — result text, ok/error state, and changed project paths;
- `loop_continue` — the model continues after receiving tool results.

`routes.py` persists tool events as role=`tool` messages for UI replay. `prompt.build_llm_messages` can reconstruct those events for the model, but `context_window.py` decides how many fit the token budget. Tool history is therefore preserved, but not always injected.

## Cancellation and deletion semantics

- Stopping a response cancels the backend streaming task, closes the upstream HTTP stream, prevents subsequent tool rounds, and sets a cancellation event for a running shell/Python process.
- Partial assistant text is persisted with `meta.interrupted=true`; if no text was produced, a small `generation_stopped` system marker is persisted instead.
- Deleting a conversation sets `deleted_at` in its metadata. The JSONL archive remains on disk.
- Deleting a project sets `archived_at` in its app metadata. Its registered filesystem root is never removed. Direct child registrations are promoted one level so they remain visible.

## Security posture

Current MVP defenses:

- local bind by default;
- optional local token;
- narrow CORS allowlist;
- project path sandbox for file preview/edit;
- project tool sandbox for model-driven file reads/writes/edits/search;
- command tools run with project cwd, timeout, output truncation, and destructive-command blacklist;
- web fetches reject loopback/private/link-local destinations and non-HTTP(S) schemes, revalidate every redirect, accept text-like content only, and cap response size;
- positive file format whitelist;
- no dynamic tool search in the public work mode; required tools are loaded directly.

Remaining hardening before wider public release:

- Windows Authenticode code signing to reduce SmartScreen friction;
- stricter token/bootstrap UX;
- release sanitizer;
- smoke tests for first-run flow;
- CI-built portable runtime instead of ad-hoc local runtime copying.
