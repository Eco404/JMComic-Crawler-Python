from __future__ import annotations

import argparse
import io
import os
import sys
import time
import zipfile
from pathlib import Path

import requests


OUTPUT_FORMATS = {"pdf", "zip", "raw", "original"}
ZIP_CONTENT_TYPES = {"application/zip", "application/x-zip-compressed"}


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


def response_content_type(response: requests.Response) -> str:
    return response.headers.get("content-type", "").split(";", 1)[0].strip().lower()


def ensure_suffix(output: Path, suffix: str) -> Path:
    if output.suffix.lower() == suffix:
        return output
    return output.with_suffix(suffix)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"cannot allocate unique output path for {path}")


def extract_pdf_files(zip_bytes: bytes, output: Path) -> list[Path]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        pdf_entries = [
            info for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".pdf")
        ]

        if not pdf_entries:
            raise RuntimeError("PDF output was requested, but the returned zip contains no PDF files")

        if len(pdf_entries) == 1:
            pdf_path = ensure_suffix(output, ".pdf")
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(archive.read(pdf_entries[0]))
            return [pdf_path]

        output_dir = output.with_suffix("")
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []

        for index, info in enumerate(pdf_entries, start=1):
            source_name = Path(info.filename).name or f"jmcomic-{index}.pdf"
            if not source_name.lower().endswith(".pdf"):
                source_name = f"{source_name}.pdf"
            pdf_path = unique_path(output_dir / source_name)
            pdf_path.write_bytes(archive.read(info))
            paths.append(pdf_path)

        return paths


def write_result_file(output: Path, content: bytes, content_type: str) -> Path:
    if content_type == "application/pdf":
        output = ensure_suffix(output, ".pdf")
    elif content_type in ZIP_CONTENT_TYPES:
        output = ensure_suffix(output, ".zip")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    return output


def download_result(base_url: str, task_id: str, output: Path, output_format: str) -> list[Path]:
    response = requests.get(
        f"{base_url}/tasks/{task_id}/archive",
        headers=request_headers(),
        timeout=120,
    )
    response.raise_for_status()

    content_type = response_content_type(response)
    content = response.content

    if output_format == "pdf" and content_type in ZIP_CONTENT_TYPES:
        return extract_pdf_files(content, output)

    return [write_result_file(output, content, content_type)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download JMComic result file via jmcomic-service.")
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
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path. Defaults to /tmp/jmcomic.pdf for pdf format and /tmp/jmcomic.zip otherwise.",
    )
    parser.add_argument("--timeout", type=int, default=1800, help="Maximum wait time in seconds.")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    try:
        base_url = args.url.rstrip("/")
        album_ids, photo_ids = parse_ids(args.ids)
        task_id = submit_task(base_url, album_ids, photo_ids, args.format)
        wait_for_task(base_url, task_id, args.timeout, args.interval)
        default_output = "/tmp/jmcomic.pdf" if args.format == "pdf" else "/tmp/jmcomic.zip"
        outputs = download_result(base_url, task_id, Path(args.output or default_output), args.format)
        for output in outputs:
            print(output)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())