import base64
return ext in ALLOWED_EXTS


def _save_content(contents: str, orig_name: str) -> tuple[str, int]:
"""Save a single dcc.Upload content string to UPLOAD_DIR.
Returns (saved_name, num_bytes)."""
if not contents:
raise ValueError("Empty content")
header, b64data = contents.split(',', 1)
data = base64.b64decode(b64data)
if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
raise ValueError(f"{orig_name}: exceeds {int(MAX_UPLOAD_MB)} MB limit")
safe = _safe_name(orig_name)
if not _is_allowed(safe):
raise ValueError(f"{orig_name}: file type not allowed")
# prevent overwrites by timestamping if needed
stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
target = UPLOAD_DIR / f"{stamp}_{safe}"
with open(target, 'wb') as f:
f.write(data)
return target.name, len(data)


def _list_files_components():
items = []
for p in sorted(UPLOAD_DIR.glob('*')):
if p.is_file():
size_kb = p.stat().st_size / 1024
items.append(html.Li([
html.A(p.name, href=f"/download/{p.name}"),
html.Span(f" ({size_kb:.1f} KB)")
]))
return html.Ul(items) if items else html.P("No files uploaded yet.")


# --- Routes ---


@server.route('/download/<path:fname>')
def download_file(fname):
return send_from_directory(UPLOAD_DIR, fname, as_attachment=True)


# --- Callbacks ---


@app.callback(
Output('status', 'children'),
Output('file-list', 'children'),
Input('uploader', 'contents'),
State('uploader', 'filename')
)
def save_uploads(contents_list, names_list):
if not contents_list:
# initial load or no upload; populate list only
return no_update, _list_files_components()


if isinstance(contents_list, str):
contents_list = [contents_list]
if isinstance(names_list, str):
names_list = [names_list]


messages = []
for contents, name in zip(contents_list, names_list or []):
try:
saved_name, nbytes = _save_content(contents, name or 'upload')
messages.append(f"✓ {name} -> {saved_name} ({nbytes} bytes)")
except Exception as e:
messages.append(f"✗ {name}: {e}")
return "\n".join(messages), _list_files_components()


if __name__ == '__main__':
app.run_server(host='0.0.0.0', port=int(os.getenv('PORT', '8000')), debug=True)
