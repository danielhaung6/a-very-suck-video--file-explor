import json
import os
from pathlib import Path


THUMBNAIL_MAP_FILE = Path(__file__).resolve().parent / "thumbnail_map.json"


def load_thumbnail_map() -> dict[str, str]:
    if not THUMBNAIL_MAP_FILE.exists():
        return {}
    try:
        data = json.loads(THUMBNAIL_MAP_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(video): str(image) for video, image in data.items()}


def save_thumbnail_map(thumbnail_map: dict[str, str]) -> None:
    tmp = THUMBNAIL_MAP_FILE.with_name(THUMBNAIL_MAP_FILE.name + ".tmp")
    tmp.write_text(
        json.dumps(thumbnail_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        os.replace(tmp, THUMBNAIL_MAP_FILE)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
