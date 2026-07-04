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
5. Download `/tasks/{task_id}/archive` to a local `.zip` file.
6. Return the local file path or attach/send it using the platform's file-sending capability.

The archive is always a zip download. With `output_format=pdf`, the zip contains generated PDF file(s). With `output_format=zip`, `raw`, or `original`, the zip contains the original downloaded image files.

## Script

Prefer using the bundled script for download-only tasks:

```bash
python skills/jmcomic-downloader/scripts/jmcomic_service_client.py 123 p456 --format pdf --output /tmp/jmcomic.zip
```

Arguments:

- Bare numeric IDs, such as `123`, become album IDs.
- `a123` becomes album ID `123`.
- `p456` becomes photo ID `456`.
- `--format pdf` is the default.
- `--format zip`, `--format raw`, or `--format original` keeps source image files.
- `--output` controls the zip path.
- `--timeout` controls total wait time in seconds.
- `--interval` controls polling interval in seconds.

The script prints the created zip path on success.

## Direct Python Pattern

Use this pattern if the script path is unavailable:

```python
import os
import time
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
output = Path("/tmp") / f"jmcomic-{task_id}.zip"
output.write_bytes(archive_resp.content)
print(output)
```

## Response Guidance

When successful, say that the archive is ready and provide or send the zip file. Mention whether it contains PDF(s) or original image files.
When the service fails, include the task ID and the error message, but do not expose internal container details.




