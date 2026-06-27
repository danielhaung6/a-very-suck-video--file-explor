import subprocess
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from pathlib import Path
from datetime import datetime

app = FastAPI()

templates = Jinja2Templates(directory="templates")

MEDIA_DIR = Path("media")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/")
async def home(request: Request):

    videos = []
    images = []

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


    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos":videos,
            "images": images
        }
    )
@app.get("/reveal/{filename}")
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

