from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Workmode Public"
DEFAULT_PORT = 8765
ROOT_DIR = Path(__file__).resolve().parents[2]


def _app_version() -> str:
    override = os.getenv("WORKMODE_APP_VERSION")
    if override:
        return override
    version_file = ROOT_DIR / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip() or "0.1.0"
    return "0.1.0"


APP_VERSION = _app_version()


def get_env_file() -> Path:
    override = os.getenv("WORKMODE_ENV_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return ROOT_DIR / ".env"


ENV_FILE = get_env_file()


def _load_dotenv() -> None:
    env_path = get_env_file()
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


_load_dotenv()


def _default_data_dir() -> Path:
    override = os.getenv("WORKMODE_PUBLIC_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt" and os.getenv("APPDATA"):
        return (Path(os.environ["APPDATA"]) / "WorkmodePublic").resolve()
    return (Path.home() / ".workmode-public").resolve()


def _allowed_origins() -> tuple[str, ...]:
    raw = os.getenv("WORKMODE_ALLOWED_ORIGINS")
    if raw:
        return tuple(part.strip() for part in raw.split(",") if part.strip())
    return (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    )


def _static_dir() -> Path:
    override = os.getenv("WORKMODE_STATIC_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return ROOT_DIR / "frontend" / "dist"


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _choice_env(name: str, default: str, choices: set[str]) -> str:
    value = os.getenv(name, default).strip()
    return value if value in choices else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    env_file: Path
    static_dir: Path
    host: str
    port: int
    allowed_origins: tuple[str, ...]
    auth_token: str | None
    model_base_url: str
    model_api_key: str | None
    model_name: str
    context_budget_tokens: int
    request_timeout_seconds: float
    mineru_api_key: str | None
    mineru_model_version: str
    mineru_language: str
    mineru_timeout_seconds: int


def load_settings() -> Settings:
    return Settings(
        data_dir=_default_data_dir(),
        env_file=get_env_file(),
        static_dir=_static_dir(),
        host=os.getenv("WORKMODE_HOST", "127.0.0.1"),
        port=int(os.getenv("WORKMODE_PORT", str(DEFAULT_PORT))),
        allowed_origins=_allowed_origins(),
        auth_token=os.getenv("WORKMODE_PUBLIC_TOKEN") or None,
        model_base_url=os.getenv("WORKMODE_MODEL_BASE_URL", "").rstrip("/"),
        model_api_key=os.getenv("WORKMODE_MODEL_API_KEY") or None,
        model_name=os.getenv("WORKMODE_MODEL_NAME", "deepseek-v4-pro"),
        context_budget_tokens=int(os.getenv("WORKMODE_CONTEXT_BUDGET_TOKENS", "700000")),
        request_timeout_seconds=float(os.getenv("WORKMODE_REQUEST_TIMEOUT_SECONDS", "120")),
        mineru_api_key=(os.getenv("WORKMODE_MINERU_API_KEY") or os.getenv("MINERU_API_KEY") or None),
        mineru_model_version=_choice_env(
            "WORKMODE_MINERU_MODEL_VERSION", "pipeline", {"pipeline", "vlm"}
        ),
        mineru_language=_choice_env(
            "WORKMODE_MINERU_LANGUAGE", "en", {"ch", "en", "ch_server", "japan"}
        ),
        mineru_timeout_seconds=_bounded_env_int(
            "WORKMODE_MINERU_TIMEOUT_SECONDS", 180, 60, 1800
        ),
    )


settings = load_settings()


def get_settings() -> Settings:
    return settings


def reload_settings() -> Settings:
    global settings
    settings = load_settings()
    return settings


def _serialize_env_value(value: str) -> str:
    if not value:
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def update_env_file(updates: dict[str, str]) -> Settings:
    """Update project .env and refresh in-process settings."""
    env_file = get_env_file()
    env_file.parent.mkdir(parents=True, exist_ok=True)
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            next_lines.append(line)
            continue
        name, _ = line.split("=", 1)
        key = name.strip()
        if key in updates:
            next_lines.append(f"{key}={_serialize_env_value(updates[key])}")
            seen.add(key)
        else:
            next_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            next_lines.append(f"{key}={_serialize_env_value(value)}")
        os.environ[key] = value

    env_file.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    return reload_settings()
