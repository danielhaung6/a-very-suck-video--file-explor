import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "cloud_config.json"
TOKENS_PATH = BASE_DIR / "cloud_tokens.json"

DEFAULT_CONFIG = {
    "google": {"client_id": "", "client_secret": "", "folder_id": "root"},
    "onedrive": {"client_id": "", "client_secret": "", "folder_path": ""},
    "dropbox": {"client_id": "", "client_secret": "", "folder_path": ""},
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_CONFIG))

    if not isinstance(data, dict):
        return json.loads(json.dumps(DEFAULT_CONFIG))

    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for provider, values in data.items():
        if provider in merged and isinstance(values, dict):
            merged[provider].update(values)
    return merged


def save_config(config: dict) -> None:
    _atomic_write(CONFIG_PATH, config)


def load_all_tokens() -> dict:
    if not TOKENS_PATH.exists():
        return {}
    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}

    provider_names = set(DEFAULT_CONFIG)
    if data and set(data) <= provider_names:
        data = {"default": data}
        _atomic_write(TOKENS_PATH, data)
    return data


def load_tokens(user_id: str) -> dict:
    all_tokens = load_all_tokens()
    tokens = all_tokens.get(user_id, {})
    return tokens if isinstance(tokens, dict) else {}


def save_tokens(user_id: str, tokens: dict) -> None:
    all_tokens = load_all_tokens()
    all_tokens[user_id] = tokens
    _atomic_write(TOKENS_PATH, all_tokens)


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
