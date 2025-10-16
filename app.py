import base64
import os
import requests
from dash import Dash, dcc, html, Input, Output, State, ctx
from dash.dependencies import ALL  # pattern-matching for dynamic components
import json
from datetime import datetime
from urllib.parse import quote
import re

# ---------- Config ----------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "atchison2024/TEST"
BRANCH = "main"
UPLOAD_DIR = "uploads"   # repo subfolder
MAX_FILE_SIZE_MB = 80    # guardrail (Contents API dislikes very large files)

# ---------- GitHub helpers ----------
API_BASE = "https://api.github.com"

def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json; charset=utf-8",
    }

def _sanitize_filename(name: str) -> str:
    # Ensure no path traversal and keep a sensible charset
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\-() ]+", "_", name)
    return name or f"file_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

def _get_file_sha_if_exists(path: str):
    url = f"{API_BASE}/repos/{REPO}/contents/{quote(path)}?ref={BRANCH}"
    r = requests.get(url, headers=_headers())
    if r.status_code == 200:
        data = r.json()
        return data.get("sha")
    if r.status_code in (404, 422):
        return None
    raise RuntimeError(f"Failed to check existing file: {r.status_code} {r.text}")

def upload_to_github(file_name: str, file_bytes: bytes, commit_msg: str = None):
    safe_name = _sanitize_filename(file_name)
    repo_path = f"{UPLOAD_DIR}/{safe_name}"

    # size guard
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return {"ok": False, "file": safe_name, "message": f"File too large (> {MAX_FILE_SIZE_MB} MB)."}

    # single base64 of raw bytes (correct for Contents API)
    content_b64 = base64.b64encode(file_bytes).decode("utf-8")

    sha = _get_file_sha_if_exists(repo_path)
    url = f"{API_BASE}/repos/{REPO}/contents/{quote(repo_path)}"
    payload = {
        "message": commit_msg or f"Upload {safe_name}",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha  # required to update existing path

    r = requests.put(url, headers=_headers(), data=json.dumps(payload))
    if r.status_code in (200, 201):
        data = r.json()
        html_url = data.get("content", {}).get("html_url")
        return {"ok": True, "file": safe_name, "url": html_url}
    try:
        err = r.json()
    except Exception:
        err = r.text
    return {"ok": False, "file": safe_name, "message": err}

# ---------- Dash app ----------
app = Dash(__name__)
server = app.server

app.layout = html.Div([
    dcc.Upload(
        id="upload-data",
        children=html.Div(["Drag and drop or select files"]),
        style={
            "width": "60%",
            "height": "60px",
            "lineHeight": "60px",
            "borderWidth": "1px",
            "borderStyle": "dashed",
            "borderRadius": "5px",
            "textAlign": "center"
        },
        multiple=True
    ),
    html.H3("Files ready to upload:"),
    html.Ul(id="file-list"),
    html.Button("Submit to GitHub", id="submit-button", n_clicks=0, style={"marginTop": "20px"}),
    html.Div(id="result", style={"marginTop": "20px"}),
    dcc.Store(id="stored-files", data={})
])

# Store uploaded files
@app.callback(
    Output("stored-files", "data"),
    Output("file-list", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    State("stored-files", "data"),
    prevent_initial_call=True
)
def store_files(contents, filenames, stored_files):
    stored = dict(stored_files or {})
    if contents:
        for content, filename in zip(contents, filenames):
            # dcc.Upload gives "data:<mime>;base64,<payload>"
            try:
                _, content_string = content.split(",", 1)
            except ValueError:
                continue
            safe_name = _sanitize_filename(filename)
            stored[safe_name] = content_string  # base64 payload string

    file_items = [
        html.Li([
            f"{fname} ",
            html.Button(
                "Delete",
                id={"type": "delete-btn", "index": fname},
                n_clicks=0,
                style={"marginLeft": "10px"}
            )
        ])
        for fname in stored.keys()
    ]
    return stored, file_items

# Handle file deletion (pattern matching: ALL)
@app.callback(
    Output("stored-files", "data", allow_duplicate=True),
    Output("file-list", "children", allow_duplicate=True),
    Input({"type": "delete-btn", "index": ALL}, "n_clicks"),
    State("stored-files", "data"),
    prevent_initial_call=True
)
def delete_file(_n_clicks_list, stored_files):
    stored = dict(stored_files or {})

    # If no specific delete button was clicked, just rebuild the current list (do NOT clear it)
    if not ctx.triggered_id:
        file_items = [
            html.Li([
                f"{f} ",
                html.Button("Delete", id={"type": "delete-btn", "index": f}, n_clicks=0, style={"marginLeft": "10px"})
            ]) for f in stored.keys()
        ]
        return stored, file_items

    # A specific delete button was clicked
    fname = ctx.triggered_id.get("index")  # {"type":"delete-btn","index":"filename"}
    if fname in stored:
        stored.pop(fname, None)

    file_items = [
        html.Li([
            f"{f} ",
            html.Button("Delete", id={"type": "delete-btn", "index": f}, n_clicks=0, style={"marginLeft": "10px"})
        ])
        for f in stored.keys()
    ]
    return stored, file_items

# Submit files to GitHub
@app.callback(
    Output("result", "children"),
    Output("stored-files", "data", allow_duplicate=True),
    Output("file-list", "children", allow_duplicate=True),
    Input("submit-button", "n_clicks"),
    State("stored-files", "data"),
    prevent_initial_call=True
)
def submit_files(n_clicks, stored_files):
    stored = dict(stored_files or {})
    if not stored:
        return "⚠️ No files to upload.", stored, []

    results = []
    for fname, content_string in stored.items():
        try:
            file_bytes = base64.b64decode(content_string)
        except Exception as e:
            results.append(html.Li([f"❌ {fname}: invalid base64 ({e})"]))
            continue

        out = upload_to_github(fname, file_bytes, commit_msg=f"Upload via Dash: {fname}")
        if out["ok"]:
            link = html.A(out["url"], href=out["url"], target="_blank", rel="noopener")
            results.append(html.Li(["✅ Uploaded ", fname, " — ", link]))
        else:
            results.append(html.Li([f"❌ {fname}: {out.get('message')}"]))

    # Clear queue after submission
    return html.Ul(results), {}, []

if __name__ == "__main__":
    app.run_server(debug=True)
