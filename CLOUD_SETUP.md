# 雲端儲存設定（CLOUD SETUP）

本專案可透過 OAuth 2.0 連結 **Google Drive、OneDrive、Dropbox**，在網頁上瀏覽、播放並上傳檔案。

整個流程分兩步：

1. 在各家的開發者後台建立應用程式，拿到 **client_id / client_secret**
2. 填入本機的 `cloud_config.json`（第一次跑會自動產生，檔案被 git 忽略）

> 本機預設位址 `http://127.0.0.1:8000`。伺服器如果換 port，callback 網址也要跟著改。

---

## 0. cloud_config.json 長這樣

```json
{
  "google":   { "client_id": "", "client_secret": "", "folder_id": "root" },
  "onedrive": { "client_id": "", "client_secret": "", "folder_path": "" },
  "dropbox":  { "client_id": "", "client_secret": "", "folder_path": "" }
}
```

- `google.folder_id`：要瀏覽/上傳的資料夾 id，`root` 是「我的雲端硬碟」根目錄。
- `onedrive.folder_path`：上傳目標資料夾，例如 `Videos`，留空＝根目錄。
- `dropbox.folder_path`：上傳目標資料夾，例如 `/Videos`，留空＝根目錄。

連上帳號後，成功存下的是 `cloud_tokens.json`（也是被 git 忽略，別外流）。

---

## 1. Google Drive

1. 到 <https://console.cloud.google.com/apis/credentials>
2. 「建立憑證」→「OAuth 用戶端 ID」→ 應用程式類型選 **網頁應用程式**
3. 授權重新導向 URI 加入：
   - `http://127.0.0.1:8000/cloud/google/callback`
4. 複製 **用戶端 ID / 用戶端密碼** 填入 `cloud_config.json` 的 `google`
5. 如果遇到「未經驗證的應用程式」畫面，點「進階」→「前往」（自己用沒差）

---

## 2. OneDrive (Microsoft)

1. 到 <https://portal.azure.com> → 搜尋 **App registrations**（應用程式註冊）
2. 「New registration」：
   - 名稱隨意
   - 支援帳戶類型選「Personal Microsoft accounts + organizational directory」
   - Redirect URI：平台 **Web**，URI 填 `http://127.0.0.1:8000/cloud/onedrive/callback`
3. 建立後到 **Certificates & secrets** → 新增 **Client secret**（密碼），複製下來（只顯示一次）
4. 到 **API permissions** → Add a permission → **Microsoft Graph** → Delegated → 勾 `Files.ReadWrite`、`offline_access`
5. 把 **Application (client) ID** 和 secret 填入 `cloud_config.json` 的 `onedrive`

> Microsoft 對 refresh token 有 90 天有效期的政策，超過時間要重新連結一次帳號。

---

## 3. Dropbox

1. 到 <https://www.dropbox.com/developers/apps>
2. 「Create app」→ 選擇 **Scoped access** → 資料夾權限選「App folder」或「Full Dropbox」都可以
3. 在 **Permissions** 勾選：`files.content.read`、`files.content.write`、`account_info.read`
4. 在 **OAuth 2** → Redirect URIs 填入 `http://127.0.0.1:8000/cloud/dropbox/callback`
5. 拿 **App key** 當 client_id、**App secret** 當 client_secret，填入 `cloud_config.json` 的 `dropbox`

---

## 4. 開始使用

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

開 <http://127.0.0.1:8000/cloud> → 切到要用的服務 → 「連結帳號」→ 瀏覽器跳出登入畫面，授權完就會自動跳回。

- 影片 / 音樂直接在頁面上播放（透過本機 proxy 串流，支援跳轉）。
- 圖片顯示縮圖。
- 上傳按鈕會把檔案丟到該服務的設定資料夾。

## 備註

- `client_secret` 和 `cloud_tokens.json` 都是敏感資料，請不要 commit。
- 播放是「本機代理」：檔案先流過你的電腦再到瀏覽器，所以跑在同台電腦上看最順。
- 上傳大檔案受各家 API 限制（Google/OneDrive 簡單上傳約 100–250MB 內沒問題，Dropbox 是 150MB）。
