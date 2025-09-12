import base64
import os
import requests

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "your-username/your-repo"
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
