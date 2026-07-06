# Video Manager

本機用的 FastAPI 媒體管理小工具。能上傳、列出、刪除影片 / 圖片 / mp3。

## 新環境直接跑

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --reload
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

打開：

```text
http://127.0.0.1:8000
```

如果 PowerShell 不給開 venv：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## 需要的東西

- Python 3.9+
- `requirements.txt` 裡的套件：`fastapi`, `uvicorn`, `python-multipart`
- Windows：`/reveal` 會用 `explorer /select,` 開檔案位置

## 記得

- 上傳檔案放在 `media/`
- `media/` 裡的大檔案被 `.gitignore` 忽略，換電腦要自己搬
- 支援：`.mp4`, `.mov`, `.mkv`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.mp3`

## 壞掉先看這裡

`uvicorn` 找不到：

```powershell
python -m uvicorn main:app --reload
```

上傳報錯：

```powershell
pip install -r requirements.txt
```

非 Windows 環境：

網站能跑，但「開啟檔案位置」那顆按鈕大概不能用，因為它寫死用 Windows Explorer。
