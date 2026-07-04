---
name: jmcomic-downloader
description: Call a private jmcomic HTTP service to search JMComic and download content. Use when a user mentions jmcomic, jm, 禁漫, jm天堂, 禁漫天堂, or asks to search, query, fetch metadata, download, package, export PDF, get a zip, or retrieve JMComic content by keyword, album ID, photo ID, or mixed IDs, especially when the jmcomic-service Docker container is available at JMCOMIC_SERVICE_URL.
---

# JMComic Downloader

Use this skill to call the private `jmcomic-service` Docker container created from this repository.

Default service URL inside Docker Compose or the same user-defined Docker bridge network:

```text
http://jmcomic-service:8000
```

Docker networking rule: AstrBot can resolve `jmcomic-service` only when the AstrBot container and the jmcomic-service container are attached to the same user-defined bridge network. In that case Docker DNS maps the service/container name `jmcomic-service` to the service container IP. Do not use `localhost` from AstrBot, because `localhost` means the AstrBot container itself.

## Trigger Terms

Treat these user terms as related to this service:

- `jmcomic`
- `jm`
- `禁漫`
- `jm天堂`
- `禁漫天堂`

## Safety

- Only call the private service URL configured by the operator.
- If the request does not include a concrete numeric ID or keyword, ask for the missing input.
- Treat IDs prefixed with `p` as photo IDs. Treat bare numeric IDs and IDs prefixed with `a` as album IDs.

## Environment

Read configuration from environment variables:

- `JMCOMIC_SERVICE_URL`, default `http://jmcomic-service:8000`

If AstrBot is in a different Compose project, attach both services to the same external Docker network and still use `http://jmcomic-service:8000`, or set `JMCOMIC_SERVICE_URL` to the actual DNS name reachable from the AstrBot container.


## Query Workflow

Use these endpoints before downloading when the user wants confirmation or asks for search/details:

- `GET /albums/{album_id}`: album detail.
- `GET /photos/{photo_id}`: photo/chapter detail.
- `GET /search?query=<keyword>&page=1`: search.
- `GET /categories?page=1&time=a&category=0&order_by=mr`: category listing.
- `GET /rankings/{day|week|month}?page=1`: rankings.

For a keyword request, call `/search`, summarize likely matches, and ask the user which one to download unless the user already made the desired ID clear.

## Download Workflow

1. Parse the user request into `album_ids` and `photo_ids`.
2. Decide `output_format`:
   - Default to `pdf`.
   - Use `zip` when the user asks for 压缩包, zip, 原文件, 原始文件, 图片文件, or raw/original files.
3. Submit `POST /tasks` with `album_ids`, `photo_ids`, and `output_format`.
4. Poll `GET /tasks/{task_id}` until `succeeded` or `failed`.
5. Download `/tasks/{task_id}/archive` to a local file.
6. If `output_format=pdf` and the downloaded file is a zip, extract the PDF file(s) from the zip and send the extracted PDF file(s), not the zip.
7. Send each result with AstrBot's file-sending interface. Do not use image/media/audio/video media interfaces for these files.
8. After the file send succeeds, delete local temporary result files, extracted PDF files, and temporary extraction directories.

With `output_format=pdf`, the service returns a PDF directly when there is exactly one generated PDF. If one request produces multiple PDF files, the service may return a zip containing those PDFs. In that case, extract the PDFs and send the PDFs individually. With `output_format=zip`, `raw`, or `original`, send the returned zip because the user asked for source/original files.

## Script

Prefer using the bundled script for download-only tasks:

```bash
python skills/jmcomic-downloader/scripts/jmcomic_service_client.py 123 p456 --format pdf --output /tmp/jmcomic.pdf
```

Arguments:

- Bare numeric IDs, such as `123`, become album IDs.
- `a123` becomes album ID `123`.
- `p456` becomes photo ID `456`.
- `--format pdf` is the default.
- `--format zip`, `--format raw`, or `--format original` keeps source image files.
- `--output` controls the result file path. Use a `.pdf` path for normal PDF output and a `.zip` path for raw/original archives.
- `--timeout` controls total wait time in seconds.
- `--interval` controls polling interval in seconds.

The script prints one result file path per line on success. In default `pdf` mode, if the service returns a zip containing PDFs, the script extracts the PDFs and prints the extracted PDF paths instead of the zip path.

## Direct Python Pattern

Use this pattern if the script path is unavailable:

```python
import io
import os
import time
import zipfile
from pathlib import Path

import requests

base_url = os.getenv("JMCOMIC_SERVICE_URL", "http://jmcomic-service:8000").rstrip("/")
# Optional detail lookup.
album_resp = requests.get(f"{base_url}/albums/123", timeout=30)
album_resp.raise_for_status()
album = album_resp.json()

payload = {"album_ids": [album["album_id"]], "photo_ids": [], "output_format": "pdf"}
resp = requests.post(f"{base_url}/tasks", json=payload, timeout=30)
resp.raise_for_status()
task_id = resp.json()["task_id"]

deadline = time.time() + 1800
while time.time() < deadline:
    status_resp = requests.get(f"{base_url}/tasks/{task_id}", timeout=30)
    status_resp.raise_for_status()
    task = status_resp.json()
    if task["status"] == "succeeded":
        break
    if task["status"] == "failed":
        raise RuntimeError(task.get("error") or "jmcomic task failed")
    time.sleep(3)
else:
    raise TimeoutError(f"jmcomic task timed out: {task_id}")

archive_resp = requests.get(f"{base_url}/tasks/{task_id}/archive", timeout=120)
archive_resp.raise_for_status()
content_type = archive_resp.headers.get("content-type", "").split(";", 1)[0].lower()
outputs = []

if content_type == "application/pdf":
    output = Path("/tmp") / f"jmcomic-{task_id}.pdf"
    output.write_bytes(archive_resp.content)
    outputs.append(output)
elif content_type in {"application/zip", "application/x-zip-compressed"}:
    extract_dir = Path("/tmp") / f"jmcomic-{task_id}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive_resp.content)) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".pdf"):
                continue
            output = extract_dir / Path(info.filename).name
            output.write_bytes(archive.read(info))
            outputs.append(output)
    if not outputs:
        raise RuntimeError("PDF mode returned a zip without PDF files")
else:
    raise RuntimeError(f"unexpected response content type: {content_type}")

for output in outputs:
    print(output)
```

## Response Guidance

When successful, send every printed result path through AstrBot's file interface. Do not use media interfaces. For default PDF output, send PDF files directly; if the backend returned a zip of PDFs, extract it and send the PDFs, not the zip. Only send zip files when the user requested zip/raw/original files. After successful sending, clean up local temporary files and extraction directories.
When the service fails, include the task ID and the error message, but do not expose internal container details.




