# Docker service wrapper

This wrapper exposes jmcomic as an HTTP service that can be called by another
container, such as AstrBot, on a private Docker network.

## Build and run

```bash
docker compose up -d --build
```

Health check:

```bash
curl http://localhost:8000/health
```

## Query APIs

The service is intended for private Docker-network use and does not enforce an API token.

Album detail:

```bash
curl http://localhost:8000/albums/123
```

Photo/chapter detail:

```bash
curl http://localhost:8000/photos/456
```

Search:

```bash
curl "http://localhost:8000/search?query=keyword&page=1"
```

Category listing:

```bash
curl "http://localhost:8000/categories?page=1&time=a&category=0&order_by=mr"
```

Rankings:

```bash
curl "http://localhost:8000/rankings/day?page=1"
```

Supported ranking periods: `day`, `week`, `month`.

## Submit a download task

The default output format is `pdf`. If the task produces exactly one PDF, the result endpoint returns that PDF directly. If it produces multiple PDFs, it returns a zip containing those PDFs.
Use `output_format: "zip"` (or `raw` / `original`) to keep original downloaded image files in a zip archive.

PDF output:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d "{\"album_ids\":[\"123\"],\"photo_ids\":[],\"output_format\":\"pdf\"}"
```

Original image archive:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d "{\"album_ids\":[\"123\"],\"photo_ids\":[],\"output_format\":\"zip\"}"
```

The response contains `task_id`.

## Poll status

```bash
curl http://localhost:8000/tasks/<task_id>
```

When `status` is `succeeded`, download the archive:

```bash
curl -L http://localhost:8000/tasks/<task_id>/archive -o jmcomic.pdf
```

## Calling from another Docker service

Put both containers on the same Docker Compose network, then call the service
name instead of `localhost`:

```text
http://jmcomic-service:8000/tasks
```

Example Python call:

```python
import time
import requests

base_url = "http://jmcomic-service:8000"

album = requests.get(f"{base_url}/albums/123", timeout=30).json()

resp = requests.post(
    f"{base_url}/tasks",
    json={"album_ids": [album["album_id"]], "photo_ids": [], "output_format": "pdf"},
    timeout=30,
)
resp.raise_for_status()
task_id = resp.json()["task_id"]

while True:
    status_resp = requests.get(f"{base_url}/tasks/{task_id}", timeout=30)
    status_resp.raise_for_status()
    task = status_resp.json()
    if task["status"] == "succeeded":
        break
    if task["status"] == "failed":
        raise RuntimeError(task["error"])
    time.sleep(3)

archive = requests.get(f"{base_url}/tasks/{task_id}/archive", timeout=120)
archive.raise_for_status()
open("jmcomic.pdf", "wb").write(archive.content)
```

## Notes

- Only expose this service on a trusted private network, or add an auth layer before publishing it externally.
- Set `JM_PROXY=http://host.docker.internal:7890` if the container must use a host proxy.
- Leave `JM_USERNAME` and `JM_PASSWORD` empty for no-login mode. Basic query/download works without login.
- PDF output requires the service image to include `img2pdf`; rebuild after dependency changes.
- The service stores task output under `/data`, so mount that path as a volume.
- Task metadata is in memory. If the container restarts, existing zip files stay on disk but task status is not restored.

## Environment variable configuration

The service exposes common jmcomic option fields through `.env`:

- `JM_CLIENT_IMPL`: client implementation, usually `api` or `html`.
- `JM_CLIENT_CACHE`: metadata cache mode, empty/null/false, `true`, `level_option`, or `level_client`.
- `JM_CLIENT_RETRY_TIMES`: request retry count.
- `JM_REQUEST_TIMEOUT`: request timeout in seconds.
- `JM_REQUEST_IMPERSONATE`: curl_cffi browser impersonation, usually `chrome`.
- `JM_DOWNLOAD_CACHE`: skip existing files in the same output path.
- `JM_IMAGE_DECODE`: decode scrambled JM images.
- `JM_IMAGE_SUFFIX`: optional converted image suffix, for example `.jpg` or `.png`.
- `JM_IMAGE_THREADS`: concurrent image download count.
- `JM_PHOTO_THREADS`: concurrent chapter/photo download count.
- `JM_DIR_RULE`: jmcomic directory rule DSL.
- `JM_NORMALIZE_ZH`: `zh-cn`, `zh-tw`, or empty.
- `JM_DEFAULT_OUTPUT_FORMAT`: `pdf`, `zip`, `raw`, or `original`.

See `.env.example` for Chinese comments and recommended defaults.
