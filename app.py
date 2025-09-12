import base64
import os
import requests
from dash import Dash, dcc, html, Input, Output, State
import base64

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "atchison2024/TEST"
BRANCH = "main"

def upload_to_github(file_name, file_bytes):
    """Upload a single file to GitHub via API (handles any binary/text)"""
    url = f"https://api.github.com/repos/{REPO}/contents/uploads/{file_name}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # ✅ Always work with raw bytes and encode them safely
    if isinstance(file_bytes, str):
        file_bytes = file_bytes.encode("utf-8")  

    content = base64.b64encode(file_bytes).decode("utf-8")

    data = {
        "message": f"Upload {file_name}",
        "content": content,
        "branch": BRANCH
    }

    response = requests.put(url, headers=headers, json=data)

    if response.status_code in [200, 201]:
        return f"✅ Uploaded {file_name}"
    else:
        return f"❌ Error {file_name}: {response.json()}"

app = Dash(__name__)
server = app.server

app.layout = html.Div([
    dcc.Upload(
        id="upload-data",
        children=html.Div(["Drag and Drop or Select Files"]),
        style={"width": "50%", "height": "60px", "border": "1px dashed black"},
        multiple=True
    ),
    html.Div(id="output")
])

@app.callback(
    Output("output", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
)
def save_files(list_of_contents, list_of_names):
    if list_of_contents is not None:
        results = []
        for contents, filename in zip(list_of_contents, list_of_names):
            content_type, content_string = contents.split(",")
            file_bytes = base64.b64decode(content_string)
            results.append(upload_to_github(filename, file_bytes))
        return html.Ul([html.Li(r) for r in results])
    return "No files uploaded yet."

if __name__ == "__main__":
    app.run_server(debug=True)
