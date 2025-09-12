import base64
import os
import requests
from dash import Dash, dcc, html, Input, Output, State
import base64

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "atchison2024/TEST"
BRANCH = "main"

def upload_to_github(file_name, file_bytes):
    url = f"https://api.github.com/repos/{REPO}/contents/uploads/{file_name}"

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(file_bytes).decode("utf-8")

    data = {
        "message": f"Upload {file_name}",
        "content": content,
        "branch": BRANCH
    }

    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        return f"✅ Uploaded {file_name} to GitHub"
    else:
        return f"❌ Error: {response.json()}"


app = Dash(__name__)
server = app.server

app.layout = html.Div([
    dcc.Upload(
        id="upload-data",
        children=html.Div(["Drag and Drop or Select a File"]),
        style={"width": "50%", "height": "60px", "border": "1px dashed black"},
        multiple=False
    ),
    html.Div(id="output")
])

@app.callback(
    Output("output", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
)
def save_file(contents, filename):
    if contents:
        content_type, content_string = contents.split(",")
        file_bytes = base64.b64decode(content_string)
        return upload_to_github(filename, file_bytes)
    return "No file uploaded yet."

if __name__ == "__main__":
    app.run_server(debug=True)
