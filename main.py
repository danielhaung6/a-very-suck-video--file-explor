from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from pathlib import Path
from datetime import datetime

app = FastAPI()

templates = Jinja2Templates(directory="templates")

MEDIA_DIR = Path("media")


@app.get("/")
async def home(request: Request):

    videos = []

    for file in MEDIA_DIR.iterdir():

        if file.suffix.lower() in [".mp4", ".mov", ".mkv"]:

            videos.append({
                "name": file.name,
                "size": round(file.stat().st_size / 1024 / 1024, 2),
                "date": datetime.fromtimestamp(
                    file.stat().st_mtime
                ).strftime("%Y-%m-%d")
            })

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos":videos
        }
    )