"""
Central config loader.

Rule from spec section 11: nothing threshold/window/cooldown-related is
hardcoded in code - it all lives in config/config.yaml. Secrets (tokens, DSNs)
come from the environment / .env, never from config.yaml, so the config file
stays safe to commit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"


def _resolve_env_file() -> Path:
    """Which dotenv file to load at import time.

    Default (unchanged production behaviour): the repo-root ``.env``. An optional
    ``SIGNALBOT_ENV_FILE`` selects a different file — QA commands set it to
    ``.env.test`` so the test env is never confused with production. A relative
    value is resolved against the repo root; an absolute path is honoured as-is.
    The path is not required to exist (``load_dotenv`` is a no-op if it does not),
    and no secret value is ever printed.
    """
    override = os.environ.get("SIGNALBOT_ENV_FILE")
    if not override:
        return ROOT_DIR / ".env"
    p = Path(override)
    return p if p.is_absolute() else (ROOT_DIR / p)


load_dotenv(_resolve_env_file())


@dataclass(frozen=True)
class Secrets:
    postgres_dsn: str
    redis_url: str
    telegram_token: str | None
    telegram_chat_id: str | None


class Config:
    """Thin wrapper around the parsed config.yaml with dict-like access."""

    def __init__(self, raw: dict[str, Any]):
        self._raw = raw

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls(raw)

    def __getitem__(self, key: str) -> Any:
        return self._raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    @property
    def symbol(self) -> str:
        return self._raw["symbol"]

    @property
    def exchanges(self) -> list[str]:
        """All exchanges the system knows about (clients + capability registry)."""
        return self._raw["exchanges"]

    @property
    def enabled_exchanges(self) -> list[str]:
        """ACTIVE subset that connects/polls/backfills/counts toward coverage.
        Falls back to all exchanges if not configured. Order follows the
        configured enabled_exchanges list."""
        return self._raw.get("enabled_exchanges", self._raw["exchanges"])

    @property
    def disabled_exchanges(self) -> list[str]:
        """Known-but-inactive exchanges (data retained, not ingested)."""
        enabled = set(self.enabled_exchanges)
        return [e for e in self._raw["exchanges"] if e not in enabled]

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw


def _build_postgres_dsn() -> str:
    """Assemble the Postgres DSN safely.

    Prefer discrete components (POSTGRES_HOST/PORT/USER/PASSWORD/DB) and
    URL-encode user/password/db so an arbitrary password (special chars like
    @ : / # ?) can never corrupt the URL. An explicit POSTGRES_DSN override is
    still honoured for advanced setups, but it is validated as a real
    postgresql:// URL — and if you use it, YOU must percent-encode the password.
    docker compose reads the same POSTGRES_* vars, so there is one source.
    """
    dsn = os.environ.get("POSTGRES_DSN")
    if dsn:
        parsed = urlparse(dsn)
        if parsed.scheme not in ("postgresql", "postgres") or not parsed.hostname:
            raise RuntimeError(
                "POSTGRES_DSN is set but is not a valid postgresql:// URL. "
                "Percent-encode special characters in the password, or unset it "
                "and use POSTGRES_HOST/PORT/USER/PASSWORD/DB instead."
            )
        return dsn

    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError(
            "Set POSTGRES_PASSWORD (or a full POSTGRES_DSN) in .env — see .env.example."
        )
    user = os.environ.get("POSTGRES_USER", "btcbot")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "btcbot")
    return (f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
            f"@{host}:{port}/{quote(db, safe='')}")


def load_secrets(cfg: Config) -> Secrets:
    infra = cfg["infra"]

    def _env(key_name: str, required: bool = True) -> str | None:
        env_var = infra[key_name]
        val = os.environ.get(env_var)
        if required and not val:
            raise RuntimeError(
                f"Missing required environment variable '{env_var}' "
                f"(see .env.example). Did you copy .env.example to .env?"
            )
        return val

    return Secrets(
        postgres_dsn=_build_postgres_dsn(),
        redis_url=_env("redis_url_env"),
        telegram_token=_env("telegram_token_env", required=False),
        telegram_chat_id=_env("telegram_chat_id_env", required=False),
    )
