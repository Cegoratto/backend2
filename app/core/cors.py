from urllib.parse import urlparse

from app.core.config import Settings, get_settings


def is_allowed_origin(origin: str | None, settings: Settings | None = None) -> bool:
    if not origin:
        return False

    cfg = settings or get_settings()
    normalized = origin.rstrip("/")

    if normalized in {item.rstrip("/") for item in cfg.cors_origin_list}:
        return True

    if normalized.endswith(".pages.dev"):
        return True

    if normalized.endswith(".workers.dev"):
        return True

    if normalized == cfg.frontend_url.rstrip("/"):
        return True

    parsed = urlparse(normalized)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"}
