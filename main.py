import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.oauth2 import credentials as user_credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

SCOPES = ["https://www.googleapis.com/auth/drive"]
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".mp3"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def drive_folder_id() -> str:
    folder_id = os.getenv("DRIVE_FOLDER_ID")
    if not folder_id:
        raise HTTPException(
            status_code=503,
            detail="Google Drive is not configured. Set DRIVE_FOLDER_ID.",
        )
    return folder_id


def get_drive():
    """Create a Drive client from either user OAuth or a service-account credential."""
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if refresh_token and client_id and client_secret:
        credentials = user_credentials.Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Drive is not configured. Set GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN, or "
                "GOOGLE_APPLICATION_CREDENTIALS."
            ),
        )

    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Unable to load Google Drive credentials.") from error
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def extension(name: str) -> str:
    return Path(name).suffix.lower()


def file_category(name: str) -> str | None:
    suffix = extension(name)
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix == ".mp3":
        return "music"
    return None


def list_drive_files() -> list[dict[str, Any]]:
    drive = get_drive()
    response = drive.files().list(
        q=f"'{drive_folder_id()}' in parents and trashed = false",
        spaces="drive",
        fields="nextPageToken, files(id, name, size, modifiedTime, mimeType, appProperties)",
        pageSize=1000,
        orderBy="modifiedTime desc",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = response.get("files", [])
    while response.get("nextPageToken"):
        response = drive.files().list(
            q=f"'{drive_folder_id()}' in parents and trashed = false",
            spaces="drive",
            fields="nextPageToken, files(id, name, size, modifiedTime, mimeType, appProperties)",
            pageSize=1000,
            orderBy="modifiedTime desc",
            pageToken=response["nextPageToken"],
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
    return files


def get_drive_file(file_id: str) -> dict[str, Any]:
    drive = get_drive()
    try:
        item = drive.files().get(
            fileId=file_id,
            fields="id,name,size,modifiedTime,mimeType,appProperties,parents",
            supportsAllDrives=True,
        ).execute()
    except Exception as error:
        raise HTTPException(status_code=404, detail="File not found.") from error
    if drive_folder_id() not in item.get("parents", []):
        raise HTTPException(status_code=404, detail="File not found.")
    return item


@app.get("/")
async def home(request: Request):
    files = await run_in_threadpool(list_drive_files)
    videos, images, musics = [], [], []
    for item in files:
        category = file_category(item["name"])
        if not category:
            continue
        common = {
            "id": item["id"],
            "name": item["name"],
            "size": round(int(item.get("size", 0)) / 1024 / 1024, 2),
            "date": datetime.fromisoformat(item["modifiedTime"].replace("Z", "+00:00")).strftime("%Y-%m-%d"),
        }
        if category == "video":
            common["thumbnail"] = None
            common["bgm_id"] = item.get("appProperties", {}).get("video_manager_bgm_id", "")
            videos.append(common)
        elif category == "image":
            common["url"] = f"/drive/files/{item['id']}/content"
            images.append(common)
        else:
            common["url"] = f"/drive/files/{item['id']}/content"
            musics.append(common)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"videos": videos, "images": images, "musics": musics},
    )


@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    def upload_one(uploaded_file: UploadFile) -> None:
        name = Path(uploaded_file.filename or "").name
        if not name or extension(name) not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {name}")
        uploaded_file.file.seek(0)
        media = MediaIoBaseUpload(
            uploaded_file.file,
            mimetype=uploaded_file.content_type or "application/octet-stream",
            resumable=True,
        )
        get_drive().files().create(
            body={"name": name, "parents": [drive_folder_id()]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()

    for uploaded_file in files:
        await run_in_threadpool(upload_one, uploaded_file)
    return RedirectResponse(url="/", status_code=303)


@app.post("/assign-bgm")
async def assign_bgm(video_id: str = Form(...), bgm_id: str = Form("")):
    video = await run_in_threadpool(get_drive_file, video_id)
    if file_category(video["name"]) != "video":
        raise HTTPException(status_code=400, detail="Invalid video.")
    if bgm_id:
        music = await run_in_threadpool(get_drive_file, bgm_id)
        if file_category(music["name"]) != "music":
            raise HTTPException(status_code=400, detail="Invalid BGM.")

    def update_bgm() -> None:
        properties = video.get("appProperties", {}).copy()
        if bgm_id:
            properties["video_manager_bgm_id"] = bgm_id
        else:
            properties.pop("video_manager_bgm_id", None)
        get_drive().files().update(
            fileId=video_id,
            body={"appProperties": properties},
            supportsAllDrives=True,
        ).execute()

    await run_in_threadpool(update_bgm)
    return RedirectResponse(url="/", status_code=303)


@app.get("/drive/files/{file_id}/content")
async def download_file(file_id: str):
    item = await run_in_threadpool(get_drive_file, file_id)

    def fetch():
        request = get_drive().files().get_media(fileId=file_id, supportsAllDrives=True)
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request, chunksize=4 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            output.seek(0)
            chunk = output.read()
            output.seek(0)
            output.truncate(0)
            if chunk:
                yield chunk

    return StreamingResponse(
        fetch(),
        media_type=item.get("mimeType") or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{item["name"]}"'},
    )


@app.post("/delete")
async def delete_file(file_id: str = Form(...)):
    await run_in_threadpool(get_drive_file, file_id)
    await run_in_threadpool(
        lambda: get_drive().files().delete(fileId=file_id, supportsAllDrives=True).execute()
    )
    return RedirectResponse(url="/", status_code=303)
