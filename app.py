import os
import base64
import pathlib
import json
from datetime import datetime

import requests
from dotenv import load_dotenv
from dash import Dash, html, dcc, Input, Output, State

# Load environment variables from .env (optional but convenient)
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")            # e.g. "YourOrg/your-repo"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_PATH_PREFIX = os.getenv("GITHUB_PATH", "uploads")  # subfolder in repo

# Basic safety checks
if not GITHUB_TOKEN or not GITHUB_REPO:
    raise RuntimeError("Please set GITHUB_TOKEN and GITHUB_REPO in your environment or .env file.")

# Local storage folder
LOCAL_UPLOAD_DIR = pathlib.Path("uploads")
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# GitHub REST API headers
GITHUB_API = "https://api.github.com"
GH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

def _github_get_file_sha(path_in_repo: str):
    """Return the current SHA of the file in GitHub if it exists, else None."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path_in_repo}"
    params = {"ref": GITHUB_BRANCH}
    r = requests.get(url, headers=GH_HEADERS, params=params)
    if r.status_code == 200:
        return r.json()["sha"]
    if r.status_code == 404:
        return None
    r.raise_for_status()

def push_file_to_github(filename: str, file_bytes: bytes) -> dict:
    """
    Create or update a file in the GitHub repo.
    Returns a dict with 'status', 'path', and optionally 'commit_url' or 'error'.
    """
    path_in_repo = f"{GITHUB_PATH_PREFIX.strip('/')}/{filename}"
    sha = _github_get_file_sha(path_in_repo)

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path_in_repo}"
    b64_content = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "message": f"Add/update via Dash: {filename}",
        "content": b64_content,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha  # required for updates

    r = requests.put(url, headers=GH_HEADERS, json=payload)
    if r.status_code in (201, 200):  # created or updated
        data = r.json()
        commit_url = data.get("commit", {}).get("html_url")
        return {"status": "ok", "path": path_in_repo, "commit_url": commit_url}
    else:
        return {"status": "error", "path": path_in_repo, "error": r.text, "code": r.status_code}

def save_locally(filename: str, file_bytes: bytes) -> pathlib.Path:
    """Save to local uploads directory and return the path."""
    safe_name = pathlib.Path(filename).name
    local_path = LOCAL_UPLOAD_DIR / safe_name
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path

def decode_upload(content: str) -> bytes:
    """Dash dcc.Upload supplies a 'data:' URL base64 string. We need the bytes."""
    # contents looks like "data:<mimetype>;base64,<base64-blob>"
    base64_str = content.split(",", 1)[1]
    return base64.b64decode(base64_str)

# ---- Dash app ----
app = Dash(__name__)
app.title = "Simple Upload to GitHub"

app.layout = html.Div(
    style={"maxWidth": 680, "margin": "40px auto", "fontFamily": "system-ui, -apple-system, Segoe UI, Roboto, Arial"},
    children=[
        html.H2("Upload files → store locally → push to GitHub"),
        dcc.Upload(
            id="upload",
            multiple=True,
            max_size=-1,  # no size cap at Dash component level
            children=html.Div(["Drag and drop or ", html.A("select files")],
                              style={"padding": "40px", "border": "2px dashed #ccc", "borderRadius": "8px"}),
        ),
        html.Div(id="status", style={"marginTop": "24px", "whiteSpace": "pre-wrap", "fontSize": "14px"}),
        html.Hr(),
        html.Div(id="meta", style={"fontSize": "12px", "color": "#555"})
    ],
)

@app.callback(
    Output("status", "children"),
    Output("meta", "children"),
    Input("upload", "contents"),
    State("upload", "filename"),
    prevent_initial_call=True
)
def handle_upload(contents_list, filenames):
    if not contents_list:
        return "No files received.", ""

    lines = []
    meta_records = []
    now = datetime.utcnow().isoformat() + "Z"

    for contents, filename in zip(contents_list, filenames):
        try:
            file_bytes = decode_upload(contents)
            local_path = save_locally(filename, file_bytes)
            result = push_file_to_github(filename, file_bytes)

            if result["status"] == "ok":
                lines.append(f"✓ {filename} → {result['path']} (committed)")
            else:
                lines.append(f"✗ {filename} → {result['path']} (error {result.get('code')}): {result.get('error')}")

            # Record a tiny bit of metadata locally (optional)
            meta_records.append({
                "filename": filename,
                "bytes": len(file_bytes),
                "saved_local": str(local_path),
                "pushed_repo_path": result.get("path"),
                "commit_url": result.get("commit_url"),
                "timestamp_utc": now,
            })
        except Exception as e:
            lines.append(f"✗ {filename}: {e}")

    # Save metadata summary locally as JSON (also pushed to GitHub for traceability)
    meta_json = json.dumps({"uploaded": meta_records}, indent=2)
    meta_name = f"upload_manifest_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    save_locally(meta_name, meta_json.encode("utf-8"))
    push_file_to_github(meta_name, meta_json.encode("utf-8"))

    return "\n".join(lines), f"Manifest contains {len(meta_records)} records. Latest: {meta_name}"

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True)
