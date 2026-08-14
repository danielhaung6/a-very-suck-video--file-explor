import urllib.parse
from pathlib import Path

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from . import config
from .providers import get_provider

router = APIRouter(prefix="/cloud", tags=["cloud"])
templates = Jinja2Templates(directory="templates")

PROVIDER_NAMES = ("google", "onedrive", "dropbox")


def _redirect_uri(request: Request, provider: str) -> str:
    base_url = str(request.base_url).rstrip("/")
    if provider == "onedrive":
        parsed = urllib.parse.urlsplit(base_url)
        port = f":{parsed.port}" if parsed.port else ""
        base_url = urllib.parse.urlunsplit(
            (parsed.scheme, f"localhost{port}", parsed.path, "", "")
        ).rstrip("/")
    return base_url + f"/cloud/{provider}/callback"


def _provider_info(name: str) -> dict:
    provider = get_provider(name)
    return {
        "name": provider.name,
        "display": provider.display,
        "configured": provider.is_configured(),
        "linked": provider.is_linked(),
    }


@router.get("")
async def cloud_home(request: Request, provider: str = "google", folder: str = ""):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")

    active = get_provider(provider)
    providers = [_provider_info(name) for name in PROVIDER_NAMES]

    files = []
    error = ""
    if not active.is_configured():
        error = f"{active.display} 尚未設定。請在 cloud_config.json 填入 client_id / client_secret（見 CLOUD_SETUP.md）。"
    elif not active.is_linked():
        error = f"{active.display} 尚未連結帳號。"
    else:
        try:
            files = await active.list_items(folder)
        except Exception as exc:
            error = f"{active.display} 讀取失敗：{exc}"

    return templates.TemplateResponse(
        request=request,
        name="cloud.html",
        context={
            "providers": providers,
            "active": _provider_info(provider),
            "folder": folder,
            "files": files,
            "error": error,
        },
    )


@router.get("/{provider}/auth")
async def auth_start(request: Request, provider: str):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")
    active = get_provider(provider)
    if not active.is_configured():
        raise HTTPException(status_code=400, detail="provider is not configured")
    return RedirectResponse(active.build_auth_uri(_redirect_uri(request, provider)))


@router.get("/{provider}/callback")
async def auth_callback(
    request: Request, provider: str, code: str = "", error: str = ""
):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth 錯誤：{error}")
    active = get_provider(provider)
    try:
        await active.exchange(code, _redirect_uri(request, provider))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"取得 token 失敗：{exc}")
    return RedirectResponse(url=f"/cloud?provider={provider}", status_code=303)


@router.get("/{provider}/logout")
async def logout(provider: str):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")
    all_tokens = config.load_tokens()
    all_tokens.pop(provider, None)
    config.save_tokens(all_tokens)
    return RedirectResponse(url=f"/cloud?provider={provider}", status_code=303)


@router.get("/{provider}/stream/{file_id}")
async def stream(request: Request, provider: str, file_id: str):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")
    active = get_provider(provider)
    try:
        url, headers = await active.stream(file_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return await _proxy(request, url, headers)


@router.get("/{provider}/thumb/{file_id}")
async def thumbnail(request: Request, provider: str, file_id: str):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")
    active = get_provider(provider)
    try:
        url, headers = await active.thumbnail(file_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return await _proxy(request, url, headers)


@router.post("/{provider}/upload")
async def upload(
    provider: str,
    folder: str = Form(""),
    files: list[UploadFile] = File(...),
):
    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail="unknown provider")
    active = get_provider(provider)
    if not (active.is_configured() and active.is_linked()):
        raise HTTPException(status_code=400, detail="provider is not linked")

    for uploaded_file in files:
        filename = Path(uploaded_file.filename or "file").name
        content = await uploaded_file.read()
        try:
            await active.upload(filename, content, folder)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"上傳失敗：{exc}")

    folder_param = f"&folder={urllib.parse.quote(folder)}" if folder else ""
    return RedirectResponse(
        url=f"/cloud?provider={provider}{folder_param}", status_code=303
    )


async def _proxy(request: Request, url: str, headers: dict):
    upstream_headers = dict(headers)
    if "range" in request.headers:
        upstream_headers["range"] = request.headers["range"]
    if "user-agent" in request.headers:
        upstream_headers["user-agent"] = request.headers["user-agent"]

    client = httpx.AsyncClient(timeout=None)
    req = client.build_request("GET", url, headers=upstream_headers)
    resp = await client.send(req, stream=True)
    if resp.status_code >= 400:
        await resp.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail="upstream fetch failed")

    forward = {}
    for key in (
        "content-type",
        "content-length",
        "content-range",
        "accept-ranges",
        "content-disposition",
        "etag",
        "cache-control",
    ):
        value = resp.headers.get(key)
        if value:
            forward[key] = value

    async def gen():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(gen(), status_code=resp.status_code, headers=forward)
