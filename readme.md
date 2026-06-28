# Video Manager

一個用 FastAPI + Jinja2 做的本機影片 / 圖片 / 音樂管理小工具。

## 新環境需要先準備

- Python 3.9 以上
- pip
- Git（如果你要用 `git clone` 下載專案）
- Windows（建議）：目前「開啟檔案位置」功能會呼叫 Windows 的 `explorer`

Python 套件依賴都寫在 `requirements.txt`：

- `fastapi`
- `uvicorn`
- `python-multipart`

## 第一次安裝

先下載或 clone 這個專案，然後在專案資料夾裡打開 PowerShell。

```powershell
cd C:\path\to\a-very-suck-video--file-explor
```

建立虛擬環境：

```powershell
python -m venv venv
```

啟用虛擬環境：

```powershell
.\venv\Scripts\Activate.ps1
```

如果 PowerShell 不讓你啟用，可以先在同一個 PowerShell 視窗執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

安裝依賴：

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 啟動專案

```powershell
uvicorn main:app --reload
```

啟動後打開：

```text
http://127.0.0.1:8000
```

也可以用這個方式啟動，會更明確使用目前虛擬環境裡的 Python：

```powershell
python -m uvicorn main:app --reload
```

## 檔案放哪裡

上傳的檔案會放在：

```text
media/
```

`media` 資料夾會在程式啟動時自動建立。專案的 `.gitignore` 已經忽略大部分上傳檔案，所以換新環境時如果需要舊影片、圖片或音樂，要另外把 `media/` 裡的檔案複製過去。

目前允許上傳的副檔名：

- 影片：`.mp4`, `.mov`, `.mkv`
- 圖片：`.jpg`, `.jpeg`, `.png`, `.webp`
- 音樂：`.mp3`

## 常見問題

### `uvicorn` 找不到

先確認虛擬環境已啟用，或改用：

```powershell
python -m uvicorn main:app --reload
```

### 上傳檔案報錯

確認有安裝 `python-multipart`：

```powershell
pip install -r requirements.txt
```

### 開啟檔案位置沒有反應

這個功能目前使用 Windows 指令：

```text
explorer /select,
```

所以新環境如果不是 Windows，網站本身可以啟動，但「開啟檔案位置」按鈕需要另外改成該系統對應的開檔案管理器方式。

### 換電腦後看不到原本的影片或圖片

上傳的媒體檔不會跟著 Git 一起保存。請把舊環境的 `media/` 資料夾內容另外複製到新環境的 `media/` 資料夾。
