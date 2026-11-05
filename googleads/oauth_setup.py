"""One-time helper: turn your OAuth client into a refresh token.

Run this on your own computer (it opens a browser for you to approve access):
    python -m googleads.oauth_setup
Then paste the printed refresh token into .env.googleads.
"""
import os

from googleads.client import load_env_file

SCOPE = "https://www.googleapis.com/auth/adwords"


def main():
    load_env_file()
    cid = os.environ.get("GOOGLE_ADS_CLIENT_ID") or input("OAuth client ID: ").strip()
    secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET") or input("OAuth client secret: ").strip()
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        {"installed": {
            "client_id": cid, "client_secret": secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }},
        scopes=[SCOPE],
    )
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print("\nGOOGLE_ADS_REFRESH_TOKEN=" + creds.refresh_token)


if __name__ == "__main__":
    main()
