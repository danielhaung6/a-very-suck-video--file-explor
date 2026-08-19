import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cloud.router import router as cloud_router
from thumbnail_map import load_thumbnail_map, save_thumbnail_map

app = FastAPI()
app.include_router(cloud_router)

MEDIA_DIR = Path("media")
BGM_MAP_FILE = Path("bgm_map.json")
MEDIA_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".mp3"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_bgm_map() -> dict[str, str]:
    if not BGM_MAP_FILE.exists():
        return {}
    try:
        data = json.loads(BGM_MAP_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(video): str(music) for video, music in data.items()}


def save_bgm_map(bgm_map: dict[str, str]) -> None:
    BGM_MAP_FILE.write_text(
        json.dumps(bgm_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_available_path(filename: str) -> Path:
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = MEDIA_DIR / safe_name
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    if not target.exists():
        return target

    counter = 1
    while True:
        candidate = MEDIA_DIR / f"{target.stem}_{counter}{target.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


@app.get("/")
async def home(request: Request):
    videos = []
    images = []
    musics = []
    bgm_map = load_bgm_map()
    thumbnail_map = load_thumbnail_map()

    for file in sorted(MEDIA_DIR.iterdir(), key=lambda item: item.name.casefold()):
        if not file.is_file():
            continue

        suffix = file.suffix.lower()
        common = {
            "name": file.name,
            "size": round(file.stat().st_size / 1024 / 1024, 2),
        }
        if suffix in VIDEO_EXTENSIONS:
            assigned_thumbnail = thumbnail_map.get(f"home:{file.name}", "")
            assigned_path = MEDIA_DIR / Path(assigned_thumbnail).name
            thumbnail = (
                f"/media/{assigned_path.name}"
                if assigned_path.is_file()
                and assigned_path.suffix.lower() in IMAGE_EXTENSIONS
                else next(
                    (
                        f"/media/{file.with_suffix(image_suffix).name}"
                        for image_suffix in IMAGE_EXTENSIONS
                        if file.with_suffix(image_suffix).exists()
                    ),
                    None,
                )
            )
            videos.append(
                {
                    **common,
                    "date": datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d"),
                    "thumbnail": thumbnail,
                    "thumbnail_name": assigned_thumbnail,
                    "bgm": bgm_map.get(file.name, ""),
                }
            )
        elif suffix in IMAGE_EXTENSIONS:
            images.append({**common, "url": f"/media/{file.name}"})
        elif suffix == ".mp3":
            musics.append({**common, "url": f"/media/{file.name}"})

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos": videos,
            "images": images,
            "musics": musics,
        },
    )


@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    for uploaded_file in files:
        target = get_available_path(uploaded_file.filename or "")
        with target.open("wb") as output:
            while chunk := await uploaded_file.read(1024 * 1024):
                output.write(chunk)
    return RedirectResponse(url="/", status_code=303)


@app.post("/assign-bgm")
async def assign_bgm(video_name: str = Form(...), bgm_name: str = Form("")):
    safe_video_name = Path(video_name).name
    safe_bgm_name = Path(bgm_name).name
    video_path = MEDIA_DIR / safe_video_name
    if not video_path.is_file() or video_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid video")

    bgm_map = load_bgm_map()
    if safe_bgm_name:
        bgm_path = MEDIA_DIR / safe_bgm_name
        if not bgm_path.is_file() or bgm_path.suffix.lower() != ".mp3":
            raise HTTPException(status_code=400, detail="Invalid BGM")
        bgm_map[safe_video_name] = safe_bgm_name
    else:
        bgm_map.pop(safe_video_name, None)
    save_bgm_map(bgm_map)
    return RedirectResponse(url="/", status_code=303)


@app.post("/assign-thumbnail")
async def assign_thumbnail(
    video_name: str = Form(...), thumbnail_name: str = Form("")
):
    safe_video_name = Path(video_name).name
    safe_thumbnail_name = Path(thumbnail_name).name
    video_path = MEDIA_DIR / safe_video_name
    if not video_path.is_file() or video_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid video")

    thumbnail_map = load_thumbnail_map()
    key = f"home:{safe_video_name}"
    if safe_thumbnail_name:
        thumbnail_path = MEDIA_DIR / safe_thumbnail_name
        if (
            not thumbnail_path.is_file()
            or thumbnail_path.suffix.lower() not in IMAGE_EXTENSIONS
        ):
            raise HTTPException(status_code=400, detail="Invalid thumbnail")
        thumbnail_map[key] = safe_thumbnail_name
    else:
        thumbnail_map.pop(key, None)
    save_thumbnail_map(thumbnail_map)
    return RedirectResponse(url="/", status_code=303)


@app.post("/delete")
async def delete_file(filename: str = Form(...)):
    file_path = MEDIA_DIR / Path(filename).name
    if file_path.is_file() and file_path.suffix.lower() in ALLOWED_EXTENSIONS:
        bgm_map = load_bgm_map()
        bgm_map.pop(file_path.name, None)
        bgm_map = {
            video: music for video, music in bgm_map.items() if music != file_path.name
        }
        save_bgm_map(bgm_map)
        thumbnail_map = load_thumbnail_map()
        thumbnail_map.pop(f"home:{file_path.name}", None)
        thumbnail_map = {
            video: image
            for video, image in thumbnail_map.items()
            if not (video.startswith("home:") and image == file_path.name)
        }
        save_thumbnail_map(thumbnail_map)
        file_path.unlink()
    return RedirectResponse(url="/", status_code=303)
