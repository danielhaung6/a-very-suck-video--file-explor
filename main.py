import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from imageio_ffmpeg import get_ffmpeg_exe
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from cloud.router import router as cloud_router
from thumbnail_map import load_thumbnail_map, save_thumbnail_map

app = FastAPI()
app.include_router(cloud_router)

SESSION_COOKIE = "vm_session"


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_id = request.cookies.get(SESSION_COOKIE, "")
    if not session_id:
        session_id = secrets.token_hex(16)
        request.state.is_new_session = True
    else:
        request.state.is_new_session = False
    request.state.session_id = session_id

    response = await call_next(request)
    if request.state.is_new_session:
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return response

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"
BGM_MAP_FILE = BASE_DIR / "bgm_map.json"
MEDIA_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/templates", StaticFiles(directory=BASE_DIR / "templates"), name="templates")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".mp3"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}


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
    tmp = BGM_MAP_FILE.with_name(BGM_MAP_FILE.name + ".tmp")
    tmp.write_text(
        json.dumps(bgm_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        os.replace(tmp, BGM_MAP_FILE)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


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


def normalize_youtube_url(value: str) -> str | None:
    url = value.strip()
    if not url:
        return None
    if "://" not in url:
        url = f"https://{url.lstrip('/')}"

    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not any(
        hostname == host or hostname.endswith(f".{host}") for host in YOUTUBE_HOSTS
    ):
        return None
    return url


def download_youtube_media(url: str, media_type: str) -> None:
    options = {
        "outtmpl": str(MEDIA_DIR.resolve() / "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "windowsfilenames": True,
        "trim_file_name": 180,
        "overwrites": False,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": get_ffmpeg_exe(),
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegMetadata", "add_metadata": True},
        ],
    }
    if media_type == "mp3":
        options.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    },
                    {"key": "EmbedThumbnail", "already_have_thumbnail": True},
                ],
            }
        )
    else:
        options.update(
            {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "EmbedThumbnail", "already_have_thumbnail": True},
                ],
            }
        )

    with YoutubeDL(options) as downloader:
        downloader.download([url])


@app.get("/")
async def home(request: Request, response: Response):
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

    flash_type = request.cookies.get("flash_type", "")
    flash_message = unquote(request.cookies.get("flash_message", ""))
    download_success = flash_message if flash_type == "success" else ""
    download_error = flash_message if flash_type == "error" else ""

    template = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos": videos,
            "images": images,
            "musics": musics,
            "download_success": download_success,
            "download_error": download_error,
        },
    )
    if flash_message:
        template.set_cookie("flash_type", "", path="/", max_age=0)
        template.set_cookie("flash_message", "", path="/", max_age=0)
    return template


@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    for uploaded_file in files:
        target = get_available_path(uploaded_file.filename or "")
        with target.open("wb") as output:
            while chunk := await uploaded_file.read(1024 * 1024):
                output.write(chunk)
    return RedirectResponse(url="/", status_code=303)


@app.post("/download-youtube")
async def download_youtube(url: str = Form(...), media_type: str = Form("mp4")):
    def flash(message: str, kind: str = "error") -> RedirectResponse:
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie("flash_type", kind, path="/")
        resp.set_cookie("flash_message", quote(message), path="/")
        return resp

    normalized_url = normalize_youtube_url(url)
    if normalized_url is None:
        return flash("請輸入有效的 YouTube 網址。")
    if media_type not in {"mp3", "mp4"}:
        return flash("請選擇 MP3 或 MP4 格式。")

    try:
        await run_in_threadpool(download_youtube_media, normalized_url, media_type)
    except (DownloadError, OSError):
        return flash("下載失敗。請確認影片可公開觀看後再試一次。")

    return flash(f"{media_type.upper()} 已下載至 media 資料夾。", kind="success")


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
