import json
import time
import urllib.parse
from pathlib import Path

import httpx

from . import config


class CloudProvider:
    name = ""
    display = ""
    authorize_url = ""
    token_url = ""
    scopes = ""

    def __init__(self) -> None:
        self.cfg = config.load_config().get(self.name, {})
        self.tokens = config.load_tokens().get(self.name, {})
        self._access_token = self.tokens.get("access_token", "")
        self._expires_at = self.tokens.get("expires_at", 0)

    def is_configured(self) -> bool:
        return bool(self.cfg.get("client_id") and self.cfg.get("client_secret"))

    def is_linked(self) -> bool:
        return bool(self.tokens.get("refresh_token"))

    def build_auth_uri(self, redirect_uri: str) -> str:
        params = {
            "client_id": self.cfg["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.scopes,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.authorize_url}?{urllib.parse.urlencode(params)}"

    async def exchange(self, code: str, redirect_uri: str) -> None:
        data = {
            "client_id": self.cfg["client_id"],
            "client_secret": self.cfg["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self.token_url, data=data)
        resp.raise_for_status()
        self._store_token(resp.json())

    async def refresh(self) -> None:
        data = {
            "client_id": self.cfg["client_id"],
            "client_secret": self.cfg["client_secret"],
            "refresh_token": self.tokens["refresh_token"],
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self.token_url, data=data)
        resp.raise_for_status()
        self._store_token(resp.json())

    async def access_token(self) -> str:
        if not self.tokens.get("refresh_token"):
            raise ValueError("provider is not linked")
        if time.time() >= self._expires_at:
            await self.refresh()
        return self._access_token

    def _store_token(self, token_data: dict) -> None:
        self._access_token = token_data.get("access_token", "")
        self._expires_at = time.time() + token_data.get("expires_in", 3600) - 60
        self.tokens = {
            "refresh_token": token_data.get(
                "refresh_token", self.tokens.get("refresh_token")
            ),
            "access_token": self._access_token,
            "expires_at": self._expires_at,
        }
        all_tokens = config.load_tokens()
        all_tokens[self.name] = self.tokens
        config.save_tokens(all_tokens)

    async def list_items(self, folder: str) -> list:
        raise NotImplementedError

    async def stream(self, file_id: str) -> tuple:
        raise NotImplementedError

    async def thumbnail(self, file_id: str) -> tuple:
        raise NotImplementedError

    async def upload(self, filename: str, content: bytes, folder: str = "") -> None:
        raise NotImplementedError


class GoogleProvider(CloudProvider):
    name = "google"
    display = "Google Drive"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    scopes = "https://www.googleapis.com/auth/drive"
    api = "https://www.googleapis.com/drive/v3"

    VIDEO_MIME = ("video/mp4", "video/quicktime", "video/x-matroska", "video/webm")
    IMAGE_MIME = ("image/jpeg", "image/png", "image/webp", "image/gif")
    AUDIO_MIME = ("audio/mpeg",)

    async def list_items(self, folder: str) -> list:
        token = await self.access_token()
        parent = folder or self.cfg.get("folder_id") or "root"
        mime_clause = "(" + " or ".join(
            f"mimeType='{m}'" for m in self.VIDEO_MIME + self.IMAGE_MIME + self.AUDIO_MIME
        ) + " or mimeType='application/vnd.google-apps.folder')"
        params = {
            "q": f"'{parent}' in parents and trashed=false and {mime_clause}",
            "fields": "files(id,name,mimeType,size,thumbnailLink),nextPageToken",
            "pageSize": 100,
        }
        files = []
        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                resp = await client.get(
                    f"{self.api}/files",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                files.extend(data.get("files", []))
                next_token = data.get("nextPageToken")
                if not next_token:
                    break
                params["pageToken"] = next_token

        result = []
        for f in files:
            if f.get("mimeType") == "application/vnd.google-apps.folder":
                result.append(
                    {
                        "name": f["name"],
                        "kind": "folder",
                        "size_mb": 0,
                        "date": "",
                        "stream_url": "",
                        "thumb_url": "",
                        "folder_url": f"/cloud?provider=google&folder={urllib.parse.quote(f['id'])}",
                    }
                )
                continue
            kind = self._kind(f.get("mimeType", ""))
            if not kind:
                continue
            size = int(f.get("size") or 0) / 1024 / 1024
            result.append(
                {
                    "name": f["name"],
                    "file_id": f["id"],
                    "kind": kind,
                    "size_mb": round(size, 2),
                    "date": "",
                    "stream_url": f"/cloud/google/stream/{urllib.parse.quote(f['id'])}",
                    "thumb_url": f.get("thumbnailLink") or "",
                    "folder_url": "",
                }
            )
        return result

    def _kind(self, mime: str) -> str:
        if mime in self.VIDEO_MIME:
            return "video"
        if mime in self.IMAGE_MIME:
            return "image"
        if mime in self.AUDIO_MIME:
            return "audio"
        return None

    async def stream(self, file_id: str) -> tuple:
        token = await self.access_token()
        return (
            f"{self.api}/files/{urllib.parse.quote(file_id)}?alt=media",
            {"Authorization": f"Bearer {token}"},
        )

    async def thumbnail(self, file_id: str) -> tuple:
        return await self.stream(file_id)

    async def upload(self, filename: str, content: bytes, folder: str = "") -> None:
        token = await self.access_token()
        parent = folder or self.cfg.get("folder_id") or "root"
        metadata = json.dumps(
            {"name": filename, "parents": [parent]}, separators=(",", ":")
        )
        boundary = "CloudUploadBoundary"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadata}\r\n"
            f"--{boundary}\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                },
                content=body,
            )
        resp.raise_for_status()


class OneDriveProvider(CloudProvider):
    name = "onedrive"
    display = "OneDrive"
    authorize_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    scopes = "files.readwrite offline_access"
    graph = "https://graph.microsoft.com/v1.0"

    VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm")
    IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    AUDIO_EXT = (".mp3",)

    async def list_items(self, folder: str) -> list:
        token = await self.access_token()
        parent = folder or self.cfg.get("folder_path") or ""
        if not parent or parent == "root" or parent == "/":
            url = f"{self.graph}/me/drive/root/children"
        elif parent.startswith("/"):
            url = (
                f"{self.graph}/me/drive/root:"
                f"{urllib.parse.quote(parent, safe='/')}:/children"
            )
        else:
            url = f"{self.graph}/me/drive/items/{urllib.parse.quote(parent)}/children"

        items = []
        async with httpx.AsyncClient(timeout=60) as client:
            next_url = url
            while next_url:
                resp = await client.get(
                    next_url, headers={"Authorization": f"Bearer {token}"}
                )
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("value", []))
                next_url = data.get("@odata.nextLink")

        result = []
        for item in items:
            name = item.get("name", "")
            if "folder" in item:
                result.append(
                    {
                        "name": name,
                        "kind": "folder",
                        "size_mb": 0,
                        "date": "",
                        "stream_url": "",
                        "thumb_url": "",
                        "folder_url": f"/cloud?provider=onedrive&folder={urllib.parse.quote(item['id'])}",
                    }
                )
                continue
            if "file" not in item:
                continue
            kind = self._kind(Path(name).suffix.lower())
            if not kind:
                continue
            size = (item.get("size") or 0) / 1024 / 1024
            result.append(
                {
                    "name": name,
                    "file_id": item["id"],
                    "kind": kind,
                    "size_mb": round(size, 2),
                    "date": item.get("lastModifiedDateTime", "")[:10],
                    "stream_url": f"/cloud/onedrive/stream/{urllib.parse.quote(item['id'])}",
                    "thumb_url": f"/cloud/onedrive/thumb/{urllib.parse.quote(item['id'])}",
                    "folder_url": "",
                }
            )
        return result

    def _kind(self, ext: str) -> str:
        if ext in self.VIDEO_EXT:
            return "video"
        if ext in self.IMAGE_EXT:
            return "image"
        if ext in self.AUDIO_EXT:
            return "audio"
        return None

    async def stream(self, file_id: str) -> tuple:
        token = await self.access_token()
        return (
            f"{self.graph}/me/drive/items/{urllib.parse.quote(file_id)}/content",
            {"Authorization": f"Bearer {token}"},
        )

    async def thumbnail(self, file_id: str) -> tuple:
        token = await self.access_token()
        return (
            f"{self.graph}/me/drive/items/{urllib.parse.quote(file_id)}/thumbnails/0/medium/content",
            {"Authorization": f"Bearer {token}"},
        )

    async def upload(self, filename: str, content: bytes, folder: str = "") -> None:
        token = await self.access_token()
        folder = folder or ""
        if folder and folder != "root":
            url = (
                f"{self.graph}/me/drive/items/{urllib.parse.quote(folder)}:"
                f"/{urllib.parse.quote(filename)}:/content"
            )
        else:
            url = f"{self.graph}/me/drive/root:/{urllib.parse.quote(filename)}:/content"
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.put(
                url, headers={"Authorization": f"Bearer {token}"}, content=content
            )
        resp.raise_for_status()


class DropboxProvider(CloudProvider):
    name = "dropbox"
    display = "Dropbox"
    authorize_url = "https://www.dropbox.com/oauth2/authorize"
    token_url = "https://api.dropboxapi.com/oauth2/token"
    scopes = "files.content.read files.content.write account_info.read"
    api = "https://api.dropboxapi.com/2"
    content = "https://content.dropboxapi.com/2"

    VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm")
    IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    AUDIO_EXT = (".mp3",)

    def build_auth_uri(self, redirect_uri: str) -> str:
        base = super().build_auth_uri(redirect_uri)
        return f"{base}&token_access_type=offline"

    async def list_items(self, folder: str) -> list:
        token = await self.access_token()
        path = folder or self.cfg.get("folder_path") or ""
        entries = []
        async with httpx.AsyncClient(timeout=60) as client:
            cursor = None
            while True:
                if cursor:
                    url = f"{self.api}/files/list_folder/continue"
                    body = {"cursor": cursor}
                else:
                    url = f"{self.api}/files/list_folder"
                    body = {"path": path, "include_media_info": True}
                resp = await client.post(
                    url, headers={"Authorization": f"Bearer {token}"}, json=body
                )
                resp.raise_for_status()
                data = resp.json()
                entries.extend(data.get("entries", []))
                if not data.get("has_more"):
                    break
                cursor = data.get("cursor")

        result = []
        for entry in entries:
            tag = entry.get(".tag")
            name = entry.get("name", "")
            path_lower = entry.get("path_lower", "")
            if tag == "folder":
                result.append(
                    {
                        "name": name,
                        "kind": "folder",
                        "size_mb": 0,
                        "date": "",
                        "stream_url": "",
                        "thumb_url": "",
                        "folder_url": f"/cloud?provider=dropbox&folder={urllib.parse.quote(path_lower)}",
                    }
                )
                continue
            if tag != "file":
                continue
            kind = self._kind(Path(name).suffix.lower())
            if not kind:
                continue
            size = (entry.get("size") or 0) / 1024 / 1024
            result.append(
                {
                    "name": name,
                    "file_id": path_lower,
                    "kind": kind,
                    "size_mb": round(size, 2),
                    "date": "",
                    "stream_url": f"/cloud/dropbox/stream/{urllib.parse.quote(path_lower)}",
                    "thumb_url": f"/cloud/dropbox/thumb/{urllib.parse.quote(path_lower)}",
                    "folder_url": "",
                }
            )
        return result

    def _kind(self, ext: str) -> str:
        if ext in self.VIDEO_EXT:
            return "video"
        if ext in self.IMAGE_EXT:
            return "image"
        if ext in self.AUDIO_EXT:
            return "audio"
        return None

    async def stream(self, file_id: str) -> tuple:
        token = await self.access_token()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.api}/files/get_temporary_link",
                headers={"Authorization": f"Bearer {token}"},
                json={"path": file_id},
            )
        resp.raise_for_status()
        return resp.json().get("link"), {}

    async def thumbnail(self, file_id: str) -> tuple:
        token = await self.access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps(
                {"path": file_id, "format": "jpeg", "size": "w256h256"},
                separators=(",", ":"),
            ),
        }
        return f"{self.content}/files/get_thumbnail", headers

    async def upload(self, filename: str, content: bytes, folder: str = "") -> None:
        token = await self.access_token()
        base = folder or self.cfg.get("folder_path") or ""
        target = f"{base}/{filename}" if base else f"/{filename}"
        if not target.startswith("/"):
            target = "/" + target
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": json.dumps(
                {"path": target, "mode": "add", "autorename": True, "mute": False},
                separators=(",", ":"),
            ),
        }
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.content}/files/upload", headers=headers, content=content
            )
        resp.raise_for_status()


PROVIDER_CLASSES = {
    "google": GoogleProvider,
    "onedrive": OneDriveProvider,
    "dropbox": DropboxProvider,
}


def get_provider(name: str) -> CloudProvider:
    if name not in PROVIDER_CLASSES:
        raise ValueError(f"unknown provider: {name}")
    return PROVIDER_CLASSES[name]()
