# Video Manager

此應用程式直接讀寫指定的 Google Drive 資料夾；EC2 不保存影片檔案。

## Google Drive 設定

1. 在 Google Cloud Console 啟用 **Google Drive API**，建立「OAuth 2.0 用戶端 ID」（Desktop app），並下載用戶端 JSON。
2. 使用你的 Google 帳號完成一次 OAuth 授權，取得 refresh token；EC2 以此 token 代表你的帳號存取 Drive。
3. 在 Google Drive 建立要存放媒體的資料夾，從資料夾網址取得 ID（`folders/` 後面的字串）。

在自己的電腦（不是 EC2）執行一次，瀏覽器會要求登入並授權，完成後終端機會輸出三個要放入 EC2 的密鑰：

```powershell
pip install -r requirements.txt
python get_refresh_token.py C:\Users\daniel\Downloads\oauth-client.json
```

若 OAuth 同意畫面維持在「測試」狀態，refresh token 通常會在 7 天後失效；長期部署前請在 Google Cloud 的 OAuth 同意畫面把你的帳號加入測試使用者，並依 Google 的要求發布應用程式。

在伺服器設定環境變數：

```powershell
$env:GOOGLE_CLIENT_ID = "你的 OAuth client ID"
$env:GOOGLE_CLIENT_SECRET = "你的 OAuth client secret"
$env:GOOGLE_REFRESH_TOKEN = "你的 OAuth refresh token"
$env:DRIVE_FOLDER_ID = "你的 Google Drive 資料夾 ID"
```

Linux / EC2：

```bash
export GOOGLE_CLIENT_ID='你的 OAuth client ID'
export GOOGLE_CLIENT_SECRET='你的 OAuth client secret'
export GOOGLE_REFRESH_TOKEN='你的 OAuth refresh token'
export DRIVE_FOLDER_ID=你的資料夾ID
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

請將以上密鑰改放在 EC2 的 systemd / AWS Secrets Manager 等機密設定，不要提交至 Git。因為這是你的個人 Drive，OAuth 比服務帳號更適合：檔案會直接使用你的 Drive 配額。

### 使用服務帳號（可選）

若你使用 Google Workspace Shared Drive，也可改為服務帳號。共用資料夾給服務帳號的 `client_email`，並設定：

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/opt/video-manager/service-account.json
export DRIVE_FOLDER_ID=你的資料夾ID
```

一般個人 Drive 的服務帳號沒有自己的儲存空間配額，可能無法上傳，因此優先使用 OAuth。

## 本機啟動

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GOOGLE_CLIENT_ID = "你的 OAuth client ID"
$env:GOOGLE_CLIENT_SECRET = "你的 OAuth client secret"
$env:GOOGLE_REFRESH_TOKEN = "你的 OAuth refresh token"
$env:DRIVE_FOLDER_ID = "你的資料夾ID"
python -m uvicorn main:app --reload
```
