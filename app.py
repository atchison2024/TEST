import os, re, base64, time, json, requests
from datetime import datetime
from dash import Dash, dcc, html, Input, Output, State, no_update

# --- Config via env vars ---
DISK_ROOT         = os.getenv("DISK_ROOT", "/var/data")             # must match render.yaml mountPath
TARGET_REPO       = os.getenv("TARGET_REPO")                         # e.g. "your-user/your-repo"
TARGET_BRANCH     = os.getenv("TARGET_BRANCH", "main")
GITHUB_BASEDIR    = os.getenv("GITHUB_BASEDIR", "uploads")           # path inside the repo
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN")                        # PAT with repo/public_repo scope
GITHUB_API        = "https://api.github.com"
MAX_BYTES         = 95 * 1024 * 1024                                 # stay below GitHub's 100 MB per-file API limit

os.makedirs(os.path.join(DISK_ROOT, GITHUB_BASEDIR), exist_ok=True)

def _safe_filename(name: str) -> str:
    name = name.strip().replace("\\", "/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:200] or f"file_{int(time.time())}"

def _github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dash-uploader"
    }

def _github_upsert(path_in_repo: str, content_bytes: bytes, commit_message: str):
    """Create or update a file via GitHub Contents API."""
    if not (GITHUB_TOKEN and TARGET_REPO):
        return False, "Server missing TARGET_REPO or GITHUB_TOKEN."

    if len(content_bytes) > MAX_BYTES:
        return False, f"File too large for direct API upload (> ~100 MB). Use Git LFS for big binaries."

    url = f"{GITHUB_API}/repos/{TARGET_REPO}/contents/{path_in_repo}"
    sha = None

    # Check if file exists to obtain SHA (required for updates)
    r_get = requests.get(url, headers=_github_headers(), params={"ref": TARGET_BRANCH})
    if r_get.status_code == 200:
        try:
            sha = r_get.json().get("sha")
        except Exception:
            pass

    payload = {
        "message": commit_message,
        "branch": TARGET_BRANCH,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
    }
    if sha:
        payload["sha"] = sha

    r_put = requests.put(url, headers=_github_headers(), data=json.dumps(payload))
    if r_put.status_code in (200, 201):
        j = r_put.json()
        blob_url = j.get("content", {}).get("html_url") or f"https://github.com/{TARGET_REPO}/blob/{TARGET_BRANCH}/{path_in_repo}"
        return True, blob_url
    else:
        try:
            j = r_put.json()
            err = j.get("message", str(j))
        except Exception:
            err = r_put.text
        return False, f"GitHub API error: {err}"

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server  # for gunicorn

app.layout = html.Div(style={"fontFamily": "system-ui", "maxWidth": 720, "margin": "40px auto"}, children=[
    html.H2("Upload → store on Render → commit to GitHub"),
    dcc.Upload(
        id="uploader",
        children=html.Div(["Drag & drop files here or ", html.A("select")]),
        multiple=True,
        style={"width": "100%", "padding": "40px", "borderWidth": "2px", "borderStyle": "dashed", "textAlign": "center"}
    ),
    html.Div(id="results", style={"marginTop": "24px", "lineHeight": "1.6"})
])

@app.callback(
    Output("results", "children"),
    Input("uploader", "contents"),
    State("uploader", "filename"),
    prevent_initial_call=True
)
def handle_upload(list_of_contents, list_of_names):
    if not list_of_contents:
        return no_update

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = []

    for content, name in zip(list_of_contents, list_of_names):
        try:
            safe = _safe_filename(name or f"file_{int(time.time())}")
            b64 = content.split(",", 1)[1]
            data = base64.b64decode(b64)

            # 1) Save to persistent disk (only under the mounted path persists across deploys)
            local_rel = f"{GITHUB_BASEDIR}/{timestamp}_{safe}"
            local_abs = os.path.join(DISK_ROOT, local_rel)
            os.makedirs(os.path.dirname(local_abs), exist_ok=True)
            with open(local_abs, "wb") as f:
                f.write(data)

            # 2) Commit to GitHub
            repo_path = local_rel  # reuse same structure in the repo
            ok, link_or_err = _github_upsert(
                path_in_repo=repo_path,
                content_bytes=data,
                commit_message=f"Add via Dash uploader: {safe}"
            )
            if ok:
                out.append(html.Div([
                    html.Strong(safe),
                    html.Span(" — saved and committed: "),
                    html.A("open on GitHub", href=link_or_err, target="_blank")
                ]))
            else:
                out.append(html.Div([
                    html.Strong(safe),
                    html.Span(" — saved locally, GitHub push failed: "),
                    html.Code(link_or_err)
                ], style={"color": "#b00020"}))

        except Exception as e:
            out.append(html.Div([
                html.Strong(name or "file"),
                html.Span(" — failed: "),
                html.Code(str(e))
            ], style={"color": "#b00020"}))

    return out

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
