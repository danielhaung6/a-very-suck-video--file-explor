"""Run locally once to authorize the Google account used by the deployed app."""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python get_refresh_token.py path/to/oauth-client.json")

    client_file = Path(sys.argv[1])
    if not client_file.is_file():
        raise SystemExit(f"OAuth client JSON not found: {client_file}")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not credentials.refresh_token:
        raise SystemExit("No refresh token returned. Run again and approve access.")

    print("Set these secret values on EC2:")
    print(f"GOOGLE_CLIENT_ID={credentials.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={credentials.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
