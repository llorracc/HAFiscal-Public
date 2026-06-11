"""Configuration loading for the Matsya client.

Reads token and server URL from:
  1. Environment variables (MATSYA_TOKEN, MATSYA_SERVER) — highest priority
  2. Config file (~/.config/matsya/config.toml)
  3. Built-in defaults
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    tomllib = None  # type: ignore[assignment]

DEFAULT_SERVER = "http://45.55.225.169:8700"


def _read_toml(path: Path) -> dict:
    """Read a simple key = "value" TOML file. Uses tomllib on 3.11+,
    falls back to a minimal line parser on 3.10."""
    if tomllib is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)
    # Minimal fallback: handles token = "..." and server = "..."
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            result[key] = val
    return result
CONFIG_DIR = Path.home() / ".config" / "matsya"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_config() -> dict[str, str]:
    """Return ``{"token": ..., "server": ...}`` merged from file + env."""
    cfg: dict[str, str] = {"token": "", "server": DEFAULT_SERVER}

    if CONFIG_FILE.exists():
        file_cfg = _read_toml(CONFIG_FILE)
        if "token" in file_cfg:
            cfg["token"] = str(file_cfg["token"])
        if "server" in file_cfg:
            cfg["server"] = str(file_cfg["server"])

    if env_token := os.environ.get("MATSYA_TOKEN"):
        cfg["token"] = env_token
    if env_server := os.environ.get("MATSYA_SERVER"):
        cfg["server"] = env_server

    return cfg


def save_config(token: str, server: str | None = None) -> Path:
    """Write *token* (and optional *server*) to the config TOML file.

    Returns the path written to.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines = [f'token = "{token}"']
    if server and server != DEFAULT_SERVER:
        lines.append(f'server = "{server}"')
    else:
        lines.append(f"# server = \"{DEFAULT_SERVER}\"")

    CONFIG_FILE.write_text("\n".join(lines) + "\n")
    CONFIG_FILE.chmod(0o600)
    return CONFIG_FILE
