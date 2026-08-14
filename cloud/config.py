import json
from pathlib import Path

CONFIG_PATH = Path("cloud_config.json")
TOKENS_PATH = Path("cloud_tokens.json")

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
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        return {}
    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_tokens(tokens: dict) -> None:
    TOKENS_PATH.write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8"
    )
