# Security policy

## Supported versions

Security fixes are provided for the latest published release.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not publish API keys, private project files, updater signing material, or exploit details in a public issue.

## Local execution boundary

Workmode Public is a local research agent with project-scoped file, shell, and Python tools. Register only directories you trust, review model-proposed changes, and treat instructions found in untrusted documents as untrusted input. The updater accepts only artifacts signed by the project's updater key.

## Official skin trust boundary

Workmode 0.7.0 accepts only `.workmode-skin` packages signed by an Ed25519 public key embedded in the application. The signature covers every package file, including `layout.css`, `visual.css`, fonts, icons, images, and the manifest. Signed skin CSS is trusted UI code: it can rearrange or visually hide interface elements, but it receives no JavaScript, HTML, network, filesystem, model, or Tauri permission entry point.

The skin signing private key is independent from the updater key and must remain in an offline backup, a Git-ignored `.release-secrets/official-skin-ed25519.pem`, or a protected CI secret. Never upload it to a Release, repository, log, issue, or user support message. A compromised skin signing key requires shipping a new application trust key and key ID before signing more skins.
