from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests


OUTPUT_FORMATS = {"pdf", "zip", "raw", "original"}


def parse_ids(raw_ids: list[str]) -> tuple[list[str], list[str]]:
    album_ids: list[str] = []
    photo_ids: list[str] = []

    for raw in raw_ids:
        item = raw.strip()
        if not item:
            continue

        prefix = item[0].lower()
        if prefix in {"a", "p"}:
            value = item[1:]
        else:
            value = item

        if not value.isdigit():
            raise ValueError(f"invalid jmcomic id: {raw}")

        if prefix == "p":
            photo_ids.append(value)
        else:
            album_ids.append(value)

    if not album_ids and not photo_ids:
        raise ValueError("at least one album or photo id is required")

    return album_ids, photo_ids


def request_headers() -> dict[str, str]:
    return {}


def submit_task(base_url: str, album_ids: list[str], photo_ids: list[str], output_format: str) -> str:
    response = requests.post(
        f"{base_url}/tasks",
        json={"album_ids": album_ids, "photo_ids": photo_ids, "output_format": output_format},
        headers=request_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["task_id"]


def wait_for_task(base_url: str, task_id: str, timeout: int, interval: float) -> dict:
    deadline = time.time() + timeout

    while time.time() < deadline:
        response = requests.get(
            f"{base_url}/tasks/{task_id}",
            headers=request_headers(),
            timeout=30,
        )
        response.raise_for_status()
        task = response.json()

        if task["status"] == "succeeded":
            return task

        if task["status"] == "failed":
            error = task.get("error") or "unknown error"
            raise RuntimeError(f"jmcomic task failed: {task_id}: {error}")

        time.sleep(interval)

    raise TimeoutError(f"jmcomic task timed out: {task_id}")


def download_archive(base_url: str, task_id: str, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        f"{base_url}/tasks/{task_id}/archive",
        headers=request_headers(),
        timeout=120,
    )
    response.raise_for_status()
    output.write_bytes(response.content)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Download JMComic archive via jmcomic-service.")
    parser.add_argument("ids", nargs="+", help="Album IDs, a-prefixed album IDs, or p-prefixed photo IDs.")
    parser.add_argument(
        "--url",
        default=os.getenv("JMCOMIC_SERVICE_URL", "http://jmcomic-service:8000"),
        help="jmcomic-service base URL.",
    )
    parser.add_argument(
        "--format",
        choices=sorted(OUTPUT_FORMATS),
        default="pdf",
        help="Output content format. pdf is the default; zip/raw/original keeps downloaded source image files.",
    )
    parser.add_argument("--output", default="/tmp/jmcomic.zip", help="Output zip path.")
    parser.add_argument("--timeout", type=int, default=1800, help="Maximum wait time in seconds.")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    try:
        base_url = args.url.rstrip("/")
        album_ids, photo_ids = parse_ids(args.ids)
        task_id = submit_task(base_url, album_ids, photo_ids, args.format)
        wait_for_task(base_url, task_id, args.timeout, args.interval)
        output = download_archive(base_url, task_id, Path(args.output))
        print(output)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

