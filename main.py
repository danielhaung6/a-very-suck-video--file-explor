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
MEDIA_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".mp3"}


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
                "thumbnail": thumbnail
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
        }
    )


@app.post("/upload") ##上傳檔案
async def upload_files(files: list[UploadFile] = File(...)):
    for uploaded_file in files:
        target = get_available_path(uploaded_file.filename or "")

        with target.open("wb") as output:
            while chunk := await uploaded_file.read(1024 * 1024):
                output.write(chunk)

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
        file_patch.unlink()


    return RedirectResponse(url="/", status_code=303)
