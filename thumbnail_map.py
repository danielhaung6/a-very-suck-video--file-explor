import json
from pathlib import Path


THUMBNAIL_MAP_FILE = Path("thumbnail_map.json")


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
    THUMBNAIL_MAP_FILE.write_text(
        json.dumps(thumbnail_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
