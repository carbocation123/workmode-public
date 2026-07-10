# Desktop distribution and updates

## What users receive

For Windows x64, distribute one file:

```text
workmode-public-<version>-windows-x86_64-setup.exe
```

The installer uses current-user installation by default, so ordinary users do not need administrator rights. It carries the frontend, backend, Python runtime, and backend dependencies; target computers do not need Node.js, Python, or Rust.

After installation:

- launch Workmode Public from the Start menu;
- close the window to stop the bundled backend and exit;
- use `Settings → Desktop application` to check, download, install, and relaunch an update;
- user data remains under `%LOCALAPPDATA%\WorkmodePublic` instead of the installation directory.

## Build-machine command

The build machine needs Node.js, Rust with the MSVC target, Visual Studio C++ Build Tools, WebView2 build support, and the prepared `backend/.venv`.

```powershell
.\scripts\build-desktop.ps1
```

The default updater endpoint is the latest GitHub Release for `carbocation123/workmode-public`; the artifact URL is version-specific. Both remain overridable through `-UpdateEndpoint` and `-ArtifactBaseUrl`.

The script performs these operations as one release command:

1. verifies version consistency;
2. runs backend and Rust contract tests;
3. stages the backend, Python base runtime, virtualenv packages, and default config;
4. builds the frontend and Tauri release binary;
5. builds the NSIS setup executable;
6. signs the updater artifact;
7. writes `latest.json` and `SHA256SUMS.txt` under `release/desktop-<version>/`;
8. checks that private signing material is absent from release output.

Use `-SkipTests` only after the same source revision has already passed the checks.

## Signing boundary

The following files are local release secrets and must never be distributed, uploaded, or committed:

```text
.release-secrets/workmode-public-updater.key
.release-secrets/updater-password.txt
```

The public key may be compiled into `tauri.conf.json`. Tauri updater signatures authenticate update content, but they are not Windows Authenticode signatures. A public release may still trigger SmartScreen until the project obtains a Windows code-signing certificate and signs the installer.

## Publishing an update

For every version, the repository owner can open `Actions → Publish Windows release → Run workflow` and enter the new version once. The workflow:

1. validates the SemVer input and synchronizes every application/package/lock-file version source;
2. commits and pushes that version change as `github-actions[bot]` when needed;
3. tests and builds with the final HTTPS `UpdateEndpoint` and `ArtifactBaseUrl`;
4. signs and uploads the setup executable plus `latest.json`;
5. creates the version tag/Release or replaces the same version's assets on a safe rerun.

The compiled updater endpoint is:

```text
https://github.com/carbocation123/workmode-public/releases/latest/download/latest.json
```

Each non-draft, non-prerelease GitHub Release must contain `latest.json` and the exact signed installer named by its `platforms.windows-x86_64.url` field.

## GitHub Actions setup

`.github/workflows/release-windows.yml` provides a manual `Publish Windows release` workflow. Before its first run, the repository owner must add these two Actions secrets in `Settings → Secrets and variables → Actions`:

- `WORKMODE_UPDATER_PRIVATE_KEY`: the complete contents of `.release-secrets/workmode-public-updater.key`;
- `WORKMODE_UPDATER_PASSWORD`: the complete contents of `.release-secrets/updater-password.txt`.

The private key must be configured by the repository owner and must never be pasted into an issue, commit, workflow file, or chat. After the secrets exist, open `Actions → Publish Windows release → Run workflow` and enter the desired version once. The workflow synchronizes source versions, builds and signs the app, then creates the `v<version>` Release or safely replaces that Release's assets when rerun.

## Legacy portable-data migration

The desktop settings page can import a 0.1.x portable folder. Migration copies only the old `data/` directory and `config/.env` into an empty desktop user-data location. It does not modify the source folder and refuses to merge over existing non-empty desktop data.
