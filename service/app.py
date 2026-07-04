from __future__ import annotations

import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

import jmcomic
from jmcomic.jm_option import DirRule


DATA_DIR = Path(os.getenv("JM_SERVICE_DATA_DIR", "/data")).resolve()
TASK_DIR = DATA_DIR / "tasks"
ARCHIVE_DIR = DATA_DIR / "archives"
OPTION_PATH = os.getenv("JM_OPTION_PATH", "/app/docker/option.yml")
MAX_WORKERS = int(os.getenv("JM_SERVICE_WORKERS", "2"))
JM_PROXY = os.getenv("JM_PROXY", "").strip()
JM_USERNAME = os.getenv("JM_USERNAME", "").strip()
JM_PASSWORD = os.getenv("JM_PASSWORD", "").strip()
JM_CLIENT_IMPL = os.getenv("JM_CLIENT_IMPL", "api").strip() or "api"
JM_CLIENT_CACHE = os.getenv("JM_CLIENT_CACHE", "").strip()
JM_CLIENT_RETRY_TIMES = os.getenv("JM_CLIENT_RETRY_TIMES", "5").strip()
JM_REQUEST_TIMEOUT = os.getenv("JM_REQUEST_TIMEOUT", "20").strip()
JM_REQUEST_IMPERSONATE = os.getenv("JM_REQUEST_IMPERSONATE", "chrome").strip() or "chrome"
JM_DOWNLOAD_CACHE = os.getenv("JM_DOWNLOAD_CACHE", "true").strip()
JM_IMAGE_DECODE = os.getenv("JM_IMAGE_DECODE", "true").strip()
JM_IMAGE_SUFFIX = os.getenv("JM_IMAGE_SUFFIX", "").strip()
JM_IMAGE_THREADS = os.getenv("JM_IMAGE_THREADS", "20").strip()
JM_PHOTO_THREADS = os.getenv("JM_PHOTO_THREADS", "4").strip()
JM_DIR_RULE = os.getenv("JM_DIR_RULE", "Bd_Aauthor_Atitle_Pindex").strip() or "Bd_Aauthor_Atitle_Pindex"
JM_NORMALIZE_ZH = os.getenv("JM_NORMALIZE_ZH", "zh-cn").strip()
JM_DEFAULT_OUTPUT_FORMAT = os.getenv("JM_DEFAULT_OUTPUT_FORMAT", "pdf").strip() or "pdf"

executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="jm-task")
tasks_lock = Lock()
tasks: dict[str, dict] = {}

app = FastAPI(title="jmcomic service", version=jmcomic.__version__)


def parse_bool_env(value: str, default: bool) -> bool:
    if value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean env value: {value!r}")


def parse_int_env(value: str, default: int) -> int:
    if value == "":
        return default
    return int(value)


def parse_nullable_env(value: str):
    if value == "":
        return None
    if value.strip().lower() in {"null", "none", "nil"}:
        return None
    return value


def parse_client_cache(value: str):
    if value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"null", "none", "false", "0", "off", "no"}:
        return None
    if normalized in {"true", "1", "on", "yes"}:
        return True
    return value


def parse_output_format(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "": "pdf",
        "pdf": "pdf",
        "zip": "zip",
        "raw": "raw",
        "original": "original",
        "image": "zip",
        "images": "zip",
        "source": "zip",
    }
    if normalized not in aliases:
        raise ValueError(f"invalid output format: {value!r}")
    return aliases[normalized]


class DownloadRequest(BaseModel):
    album_ids: list[str] = Field(default_factory=list)
    photo_ids: list[str] = Field(default_factory=list)
    output_format: Literal["pdf", "zip", "raw", "original"] = parse_output_format(JM_DEFAULT_OUTPUT_FORMAT)

    @model_validator(mode="after")
    def require_ids(self):
        if not self.album_ids and not self.photo_ids:
            raise ValueError("album_ids or photo_ids is required")
        return self


class TaskResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str
    updated_at: str
    album_ids: list[str]
    photo_ids: list[str]
    output_format: Literal["pdf", "zip", "raw", "original"]
    archive_url: str | None = None
    error: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_task(task_id: str) -> TaskResponse:
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return TaskResponse(**task)


def set_task(task_id: str, **updates):
    with tasks_lock:
        task = tasks[task_id]
        task.update(updates)
        task["updated_at"] = now_iso()


def apply_runtime_env(option):
    option.client.src_dict["impl"] = JM_CLIENT_IMPL
    option.client.src_dict["retry_times"] = parse_int_env(JM_CLIENT_RETRY_TIMES, 5)
    option.client.src_dict["cache"] = parse_client_cache(JM_CLIENT_CACHE)

    metadata = option.client.postman.meta_data.src_dict
    metadata["timeout"] = parse_int_env(JM_REQUEST_TIMEOUT, 20)
    metadata["impersonate"] = JM_REQUEST_IMPERSONATE
    metadata["proxies"] = parse_nullable_env(JM_PROXY)

    option.download.src_dict["cache"] = parse_bool_env(JM_DOWNLOAD_CACHE, True)
    option.download.image.src_dict["decode"] = parse_bool_env(JM_IMAGE_DECODE, True)
    option.download.image.src_dict["suffix"] = parse_nullable_env(JM_IMAGE_SUFFIX)
    option.download.threading.src_dict["image"] = parse_int_env(JM_IMAGE_THREADS, 20)
    option.download.threading.src_dict["photo"] = parse_int_env(JM_PHOTO_THREADS, 4)

    if JM_USERNAME or JM_PASSWORD:
        if not JM_USERNAME or not JM_PASSWORD:
            raise ValueError("JM_USERNAME and JM_PASSWORD must be set together")
        client = option.build_jm_client()
        client.login(JM_USERNAME, JM_PASSWORD)
        option.update_cookies(dict(client["cookies"]))


def build_option(base_dir: Path):
    if OPTION_PATH and Path(OPTION_PATH).exists():
        option = jmcomic.create_option_by_file(OPTION_PATH)
    else:
        option = jmcomic.JmOption.default()

    option = option.copy_option()
    option.dir_rule = DirRule(
        rule=JM_DIR_RULE,
        base_dir=str(base_dir),
        normalize_zh=parse_nullable_env(JM_NORMALIZE_ZH),
    )
    apply_runtime_env(option)
    return option


def build_task_option(task_download_dir: Path):
    return build_option(task_download_dir)


def build_query_client():
    option = build_option(DATA_DIR / "query")
    return option.new_jm_client(cache="level_option")


def safe_json(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe_json(v) for v in value]
    return str(value)


def album_url(album_id: str) -> str:
    try:
        return jmcomic.JmcomicText.format_album_url(album_id)
    except Exception:
        return f"https://18comic.vip/album/{album_id}/"


def album_cover_url(album_id: str) -> str:
    try:
        return jmcomic.JmcomicText.get_album_cover_url(album_id)
    except Exception:
        return ""


def serialize_album(album) -> dict:
    episodes = []
    for item in album.episode_list:
        if len(item) >= 3:
            episodes.append({
                "photo_id": str(item[0]),
                "index": int(item[1]),
                "title": str(item[2]).strip(),
            })

    return {
        "album_id": album.album_id,
        "id": album.album_id,
        "name": album.name,
        "title": album.name,
        "description": album.description,
        "author": album.author,
        "authors": album.authors,
        "tags": album.tags,
        "works": album.works,
        "actors": album.actors,
        "page_count": album.page_count,
        "pub_date": album.pub_date,
        "update_date": album.update_date,
        "likes": album.likes,
        "views": album.views,
        "comment_count": album.comment_count,
        "episode_count": len(album.episode_list),
        "episodes": episodes,
        "related": safe_json(album.related_list),
        "url": album_url(album.album_id),
        "cover_url": album_cover_url(album.album_id),
    }


def serialize_photo(photo, include_images: bool = True) -> dict:
    image_names = list(photo.page_arr or [])
    data: dict[str, Any] = {
        "photo_id": photo.photo_id,
        "id": photo.photo_id,
        "album_id": photo.album_id,
        "name": photo.name,
        "title": photo.name,
        "author": photo.author,
        "tags": photo.tags,
        "sort": photo.sort,
        "album_index": photo.album_index,
        "scramble_id": photo.scramble_id,
        "image_count": len(image_names),
        "image_names": image_names,
    }

    if photo.from_album is not None:
        data["album"] = {
            "album_id": photo.from_album.album_id,
            "name": photo.from_album.name,
            "author": photo.from_album.author,
            "page_count": photo.from_album.page_count,
            "url": album_url(photo.from_album.album_id),
            "cover_url": album_cover_url(photo.from_album.album_id),
        }

    if include_images and image_names and photo.data_original_domain:
        images = []
        for index, name in enumerate(image_names, start=1):
            images.append({
                "index": index,
                "filename": name,
                "url": photo.get_img_data_original(name),
            })
        data["images"] = images

    return data


def serialize_page(page, page_number: int) -> dict:
    items = []
    for album_id, info in page.content:
        item = {"album_id": str(album_id)}
        if isinstance(info, dict):
            item.update(safe_json(info))
        else:
            item["info"] = safe_json(info)
        item.setdefault("url", album_url(item["album_id"]))
        item.setdefault("cover_url", album_cover_url(item["album_id"]))
        items.append(item)

    data = {
        "page": page_number,
        "page_size": page.page_size,
        "page_count": page.page_count,
        "total": int(page.total),
        "items": items,
    }

    if getattr(page, "is_single_album", False):
        data["album"] = serialize_album(page.single_album)

    return data


def zip_directory(source_dir: Path, output_base: Path) -> Path:
    archive = shutil.make_archive(str(output_base), "zip", root_dir=source_dir)
    return Path(archive)


def has_downloaded_files(source_dir: Path) -> bool:
    return source_dir.exists() and any(path.is_file() for path in source_dir.rglob("*"))


def build_download_feature(output_format: str, task_download_dir: Path):
    if output_format != "pdf":
        return None
    return jmcomic.Feature.export_pdf(
        pdf_dir=str(task_download_dir),
        delete_original_file=True,
    )


def require_successful_batch(result, requested_ids: list[str], kind: str):
    if requested_ids and not result:
        raise RuntimeError(
            f"{kind} download produced no successful results for ids: {requested_ids}. "
            "Check jmcomic logs, network/proxy settings, and whether the IDs are valid."
        )


def run_download_task(task_id: str):
    task_download_dir = TASK_DIR / task_id / "downloads"
    archive_base = ARCHIVE_DIR / task_id

    try:
        task_download_dir.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        set_task(task_id, status="running")
        with tasks_lock:
            album_ids = list(tasks[task_id]["album_ids"])
            photo_ids = list(tasks[task_id]["photo_ids"])
            output_format = tasks[task_id]["output_format"]

        option = build_task_option(task_download_dir)
        feature = build_download_feature(output_format, task_download_dir)

        if album_ids:
            album_result = jmcomic.download_album(album_ids, option, extra=feature)
            require_successful_batch(album_result, album_ids, "album")
        if photo_ids:
            photo_result = jmcomic.download_photo(photo_ids, option, extra=feature)
            require_successful_batch(photo_result, photo_ids, "photo")

        if not has_downloaded_files(task_download_dir):
            raise RuntimeError(
                "download finished without any output files. "
                "Check jmcomic logs, network/proxy settings, and whether the IDs are valid."
            )

        archive_path = zip_directory(task_download_dir, archive_base)
        set_task(
            task_id,
            status="succeeded",
            archive_path=str(archive_path),
            archive_url=f"/tasks/{task_id}/archive",
        )
    except Exception as exc:
        set_task(task_id, status="failed", error=repr(exc))


def service_error(exc: Exception):
    raise HTTPException(status_code=502, detail=repr(exc)) from exc


@app.on_event("startup")
def startup():
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok", "version": jmcomic.__version__}


@app.get("/albums/{album_id}")
def get_album(album_id: str):
    try:
        client = build_query_client()
        return serialize_album(client.get_album_detail(album_id))
    except Exception as exc:
        service_error(exc)


@app.get("/photos/{photo_id}")
def get_photo(photo_id: str, include_images: bool = True):
    try:
        client = build_query_client()
        return serialize_photo(client.get_photo_detail(photo_id), include_images=include_images)
    except Exception as exc:
        service_error(exc)


@app.get("/search")
def search(
    query: str = Query(..., min_length=1),
    page: int = 1,
    main_tag: int = 0,
    order_by: str = jmcomic.JmMagicConstants.ORDER_BY_LATEST,
    time: str = jmcomic.JmMagicConstants.TIME_ALL,
    category: str = jmcomic.JmMagicConstants.CATEGORY_ALL,
    sub_category: str | None = None,
):
    try:
        client = build_query_client()
        result = client.search(query, page, main_tag, order_by, time, category, sub_category)
        return serialize_page(result, page)
    except Exception as exc:
        service_error(exc)


@app.get("/categories")
def categories(
    page: int = 1,
    time: str = jmcomic.JmMagicConstants.TIME_ALL,
    category: str = jmcomic.JmMagicConstants.CATEGORY_ALL,
    order_by: str = jmcomic.JmMagicConstants.ORDER_BY_LATEST,
    sub_category: str | None = None,
):
    try:
        client = build_query_client()
        result = client.categories_filter(page, time, category, order_by, sub_category)
        return serialize_page(result, page)
    except Exception as exc:
        service_error(exc)


@app.get("/rankings/{period}")
def rankings(period: Literal["day", "week", "month"], page: int = 1, category: str = jmcomic.JmMagicConstants.CATEGORY_ALL):
    try:
        client = build_query_client()
        if period == "day":
            result = client.day_ranking(page, category)
        elif period == "week":
            result = client.week_ranking(page, category)
        else:
            result = client.month_ranking(page, category)
        return serialize_page(result, page)
    except Exception as exc:
        service_error(exc)


@app.post("/tasks", response_model=TaskResponse)
def create_task(request: DownloadRequest):
    task_id = uuid.uuid4().hex
    timestamp = now_iso()

    with tasks_lock:
        tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "created_at": timestamp,
            "updated_at": timestamp,
            "album_ids": request.album_ids,
            "photo_ids": request.photo_ids,
            "output_format": request.output_format,
            "archive_url": None,
            "archive_path": None,
            "error": None,
        }

    executor.submit(run_download_task, task_id)
    return snapshot_task(task_id)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str):
    return snapshot_task(task_id)


@app.get("/tasks/{task_id}/archive")
def get_archive(task_id: str):
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        if task["status"] != "succeeded":
            raise HTTPException(status_code=409, detail=f"task is {task['status']}")
        archive_path = task.get("archive_path")

    if not archive_path or not Path(archive_path).is_file():
        raise HTTPException(status_code=404, detail="archive not found")

    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"jmcomic-{task_id}.zip",
    )






