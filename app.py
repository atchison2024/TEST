import base64
import os
import requests
from dash import Dash, dcc, html, Input, Output, State, ctx

# GitHub credentials
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "atchison2024/TEST"
BRANCH = "main"

# Upload function
def upload_to_github(file_name, file_bytes):
    url = f"https://api.github.com/repos/{REPO}/contents/uploads/{file_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/vnd.github.v3+json"
    }

    if isinstance(file_bytes, str):
        file_bytes = file_bytes.encode("utf-8")

    content = base64.b64encode(file_bytes).decode("utf-8")
    if isinstance(content, bytes):
        encoded_content = base64.b64encode(content).decode("utf-8")
    elif isinstance(content, str):
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    else:
        raise TypeError(f"'content' must be str or bytes, not {type(content).__name__}")
    
    data = {
        "message": f"Upload {file_name}",
        "content": encoded_content,
        "branch": BRANCH
    }

    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        return f"✅ Uploaded {file_name}"
    else:
        return f"❌ Error {file_name}: {response.json()}"

# Dash app
app = Dash(__name__)
server = app.server

app.layout = html.Div([
    dcc.Upload(
        id="upload-data",
        children=html.Div(["Drag and Drop or Select Files"]),
        style={
            "width": "60%",
            "height": "60px",
            "lineHeight": "60px",
            "borderWidth": "1px",
            "borderStyle": "dashed",
            "borderRadius": "5px",
            "textAlign": "center"
        },
        multiple=True  # ✅ allow multiple files
    ),
    html.H3("Files ready to upload:"),
    html.Ul(id="file-list"),  # ✅ list of files
    html.Button("Submit to GitHub", id="submit-button", n_clicks=0, style={"marginTop": "20px"}),
    html.Div(id="result", style={"marginTop": "20px"}),
    dcc.Store(id="stored-files", data={})  # ✅ keep uploaded files in memory
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
    if contents is not None:
        for content, filename in zip(contents, filenames):
            _, content_string = content.split(",")
            stored_files[filename] = content_string  # store base64 content

    # Create file list with delete buttons
    file_items = [
        html.Li([
            f"{fname} ",
            html.Button("Delete", id={"type": "delete-btn", "index": fname}, n_clicks=0, style={"marginLeft": "10px"})
        ])
        for fname in stored_files.keys()
    ]
    return stored_files, file_items

# Handle file deletion
@app.callback(
    Output("stored-files", "data", allow_duplicate=True),
    Output("file-list", "children", allow_duplicate=True),
    Input({"type": "delete-btn", "index": str}, "n_clicks"),
    State("stored-files", "data"),
    prevent_initial_call=True
)
def delete_file(n_clicks, stored_files):
    if not ctx.triggered_id:
        return stored_files, []
    fname = ctx.triggered_id["index"]
    if fname in stored_files:
        stored_files.pop(fname)

    file_items = [
        html.Li([
            f"{f} ",
            html.Button("Delete", id={"type": "delete-btn", "index": f}, n_clicks=0, style={"marginLeft": "10px"})
        ])
        for f in stored_files.keys()
    ]
    return stored_files, file_items

# Submit files to GitHub
@app.callback(
    Output("result", "children"),
    Input("submit-button", "n_clicks"),
    State("stored-files", "data"),
    prevent_initial_call=True
)
def submit_files(n_clicks, stored_files):
    if not stored_files:
        return "⚠️ No files to upload."
    
    results = []
    for fname, content_string in stored_files.items():
        file_bytes = base64.b64decode(content_string)
        results.append(upload_to_github(fname, file_bytes))

    return html.Ul([html.Li(r) for r in results])

if __name__ == "__main__":
    app.run_server(debug=True)
