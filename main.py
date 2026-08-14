import json
import subprocess
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse


from pathlib import Path
from datetime import datetime

app = FastAPI()

templates = Jinja2Templates(directory="templates")

MEDIA_DIR = Path("media")
BGM_MAP_FILE = Path("bgm_map.json")
MEDIA_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".mp3"}


def load_bgm_map() -> dict[str, str]:
    if not BGM_MAP_FILE.exists():
        return {}

    try:
        with BGM_MAP_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        str(video_name): str(bgm_name)
        for video_name, bgm_name in data.items()
    }


def save_bgm_map(bgm_map: dict[str, str]) -> None:
    with BGM_MAP_FILE.open("w", encoding="utf-8") as file:
        json.dump(bgm_map, file, ensure_ascii=False, indent=2)


def get_available_path(filename: str) -> Path:   ##狀態顯示
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = MEDIA_DIR / safe_name
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = MEDIA_DIR / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


@app.get("/") ##影片，照片，BGM
async def home(request: Request):

    videos = []
    images = []
    musics = []
    bgm_map = load_bgm_map()

    for file in MEDIA_DIR.iterdir():

        if file.suffix.lower() in [".mp4", ".mov", ".mkv"]:
            thumbnail = None

            for image_suffix in [".jpg", ".jpeg", ".png", ".webp"]:
                image_file = file.with_suffix(image_suffix)
                if image_file.exists():
                    thumbnail = f"/media/{image_file.name}"
                    break

            videos.append({
                "name": file.name,
                "size": round(file.stat().st_size / 1024 / 1024, 2),
                "date": datetime.fromtimestamp(
                    file.stat().st_mtime
                ).strftime("%Y-%m-%d"),
                "thumbnail": thumbnail,
                "bgm": bgm_map.get(file.name, "")
            })

        if file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            images.append({
                "name": file.name,
                "size": round(file.stat().st_size / 1024 /1024, 2),
                "url": f"/media/{file.name}"
            })
        
        if file.suffix.lower() in [".mp3"]:
            musics.append({
                "name": file.name,
                "size": round(file.stat().st_size / 1024 /1024 ,2),
                "url": f"/media/{file.name}"
            })


    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos":videos,
            "images": images,
            "musics": musics
        })


@app.post("/upload") ##上傳檔案
async def upload_files(files: list[UploadFile] = File(...)):
    for uploaded_file in files:
        target = get_available_path(uploaded_file.filename or "")

        with target.open("wb") as output:
            while chunk := await uploaded_file.read(1024 * 1024):
                output.write(chunk)

    return RedirectResponse(url="/", status_code=303)


@app.post("/assign-bgm")
async def assign_bgm(
    video_name: str = Form(...),
    bgm_name: str = Form("")
):
    safe_video_name = Path(video_name).name
    safe_bgm_name = Path(bgm_name).name
    video_path = MEDIA_DIR / safe_video_name

    if (
        not video_path.exists()
        or video_path.suffix.lower() not in [".mp4", ".mov", ".mkv"]
    ):
        raise HTTPException(status_code=400, detail="Invalid video")

    bgm_map = load_bgm_map()

    if safe_bgm_name:
        bgm_path = MEDIA_DIR / safe_bgm_name
        if not bgm_path.exists() or bgm_path.suffix.lower() != ".mp3":
            raise HTTPException(status_code=400, detail="Invalid BGM")

        bgm_map[safe_video_name] = safe_bgm_name
    else:
        bgm_map.pop(safe_video_name, None)

    save_bgm_map(bgm_map)
    return RedirectResponse(url="/", status_code=303)


@app.get("/reveal/{filename}") ##刪檔案
async def reveal_file(filename:str):

    file_path = MEDIA_DIR / filename

    if file_path.exists():

        subprocess.run([
            "explorer",
            "/select,",
            str(file_path.resolve())
        ])

        return RedirectResponse(url="/")
    return{"success":False}
@app.post("/delete")
async def delete_file(filename: str = Form(...)):
    file_patch = MEDIA_DIR / Path(filename).name

    if file_patch.exists() and file_patch.is_file():
        bgm_map = load_bgm_map()
        bgm_map.pop(file_patch.name, None)

        for video_name, bgm_name in list(bgm_map.items()):
            if bgm_name == file_patch.name:
                bgm_map.pop(video_name, None)

        save_bgm_map(bgm_map)
        file_patch.unlink()


    return RedirectResponse(url="/", status_code=303)
