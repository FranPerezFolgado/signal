"""
One-shot script to obtain a Spotify refresh token via OAuth2.
Run with: uv run python scripts/get_spotify_token.py

Setup: in your Spotify app settings add this redirect URI:
    http://localhost:8888/callback
"""

import base64
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = "http://localhost:8888/callback"
SCOPE = "user-follow-read"

print("Spotify Refresh Token Generator")
print("=" * 40)
print("Make sure http://localhost:8888/callback is registered in your Spotify app.")
print()
client_id = input("Client ID: ").strip()
client_secret = input("Client Secret: ").strip()

auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
    {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
)

print("\nOpening Spotify login in your browser...")
webbrowser.open(auth_url)
print("(If it did not open, visit this URL manually:)")
print(auth_url)
print()
print("After you log in, the browser will redirect to localhost:8888 and show an error.")
print("That is expected. Copy the FULL URL from the address bar and paste it here.")
print()

callback_url = input("Paste the full redirect URL: ").strip()
parsed = urllib.parse.urlparse(callback_url)
params = urllib.parse.parse_qs(parsed.query)

if "code" not in params:
    print("No 'code' found in that URL. Make sure you copied the full address bar URL.")
    raise SystemExit(1)

code = params["code"][0]
credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
resp = requests.post(
    "https://accounts.spotify.com/api/token",
    headers={"Authorization": f"Basic {credentials}"},
    data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    },
    timeout=10,
)

if resp.status_code != 200:
    # Do not print resp.text — it may echo back OAuth credentials in some error responses
    print(f"\nToken exchange failed with status {resp.status_code}.")
    print("Check that your Client ID and Client Secret are correct.")
    raise SystemExit(1)

data = resp.json()
print("\n" + "=" * 40)
print("WARNING: Run this script only in a private terminal.")
print("Do not run it in CI or shared sessions — credentials appear in output.")
print("=" * 40)
print("Add these to your .env file:")
print(f"SPOTIFY_CLIENT_ID={client_id}")
# Client secret is already known to you — only REFRESH_TOKEN is new
print(f"SPOTIFY_CLIENT_SECRET=<your secret>")
print(f"SPOTIFY_REFRESH_TOKEN={data['refresh_token']}")
print("=" * 40)
