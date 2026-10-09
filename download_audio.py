#!/usr/bin/env python3
"""Download the original YouTube audio listed in YouChorale's info.csv."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def load_links(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle, delimiter="\t"))
    seen = set()
    for row in records:
        video_id = row["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError(f"Invalid video ID: {video_id!r}")
        url = urlparse(row["link"])
        if url.scheme != "https" or url.hostname not in {"www.youtube.com", "youtube.com"}:
            raise ValueError(f"Invalid YouTube link for {video_id}")
        if parse_qs(url.query).get("v") != [video_id] or video_id in seen:
            raise ValueError(f"Duplicate or mismatched video ID: {video_id}")
        seen.add(video_id)
    return records


def valid_audio(path: Path) -> bool:
    """Check the audio header and decode the entire downloaded file."""
    if (not path.is_file() or path.stat().st_size == 0
            or ".part" in path.name or path.suffix == ".ytdl"):
        return False
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=sample_rate,channels:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        stream = data["streams"][0]
        if (result.returncode or not math.isfinite(duration) or duration <= 0
                or int(stream["sample_rate"]) <= 0 or int(stream["channels"]) <= 0):
            return False
        decoded = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
             "-map", "0:a:0", "-f", "null", "-"],
            capture_output=True, timeout=max(120, duration * 2),
        )
        return decoded.returncode == 0
    except (KeyError, IndexError, ValueError, subprocess.SubprocessError):
        return False


def download(row: dict[str, str], output: Path, retries: int, cookies: Path | None,
             node: str | None) -> Path:
    from yt_dlp import YoutubeDL

    item_dir = output / row["id"]
    item_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(item_dir.glob("source.*")):
        if valid_audio(path):
            return path
    errors = []
    for attempt in range(retries + 1):
        options = {
            "format": "bestaudio/best", "format_sort": ["asr", "abr"],
            "outtmpl": str(item_dir / "source.%(ext)s"), "noplaylist": True,
            "retries": 0, "fragment_retries": 0, "extractor_retries": 0,
            "file_access_retries": 0, "socket_timeout": 30,
            "quiet": True, "no_warnings": False, "noprogress": True,
            # Prefer IPv4, which recovered a failed request during Jupiter setup.
            "source_address": "0.0.0.0",
        }
        if node:
            options["js_runtimes"] = {"node": {"path": node}}
        if cookies:
            options["cookiefile"] = str(cookies.resolve())
        try:
            # Discard corrupt completed files. yt-dlp resumes its own .part files.
            for path in item_dir.glob("source.*"):
                if ".part" not in path.name and path.suffix != ".ytdl" and not valid_audio(path):
                    path.unlink()
            print(f"{row['id']}: attempt {attempt + 1}/{retries + 1}", flush=True)
            with YoutubeDL(options) as downloader:
                downloader.download([row["link"]])
            for path in sorted(item_dir.glob("source.*")):
                if valid_audio(path):
                    return path
            raise RuntimeError("Download produced no complete decodable audio")
        except Exception as exc:
            message = re.sub(r"\x1b\[[0-9;]*m", "", str(exc))
            errors.append(message)
            print(f"{row['id']}: {message}", file=sys.stderr, flush=True)
            if attempt < retries:
                time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"{retries + 1} attempts failed: {errors[-1]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--info", type=Path, default=Path(__file__).with_name("info.csv"))
    parser.add_argument("--retries", type=int, default=3,
                        help="Retries after the initial attempt (default: 3)")
    parser.add_argument("--cookies", type=Path)
    parser.add_argument("--id", dest="ids", action="append",
                        help="Download one video ID; repeat to select more")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.retries < 0 or (args.limit is not None and args.limit < 1):
        parser.error("retries must be nonnegative and limit must be positive")
    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            parser.error(f"{executable} must be available on PATH")
    rows = load_links(args.info)
    if args.ids:
        wanted = set(args.ids)
        missing = wanted - {row["id"] for row in rows}
        if missing:
            parser.error(f"Unknown IDs: {sorted(missing)}")
        rows = [row for row in rows if row["id"] in wanted]
    if args.limit:
        rows = rows[:args.limit]
    args.output = args.output.expanduser().resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    failed = []
    for index, row in enumerate(rows, 1):
        try:
            path = download(row, args.output, args.retries, args.cookies, shutil.which("node"))
            print(f"[{index}/{len(rows)}] OK {row['id']} {path.name}", flush=True)
        except Exception as exc:
            failed.append((row["id"], str(exc)))
            print(f"[{index}/{len(rows)}] FAILED {row['id']}: {exc}", flush=True)
    for video_id, reason in failed:
        print(f"UNAVAILABLE\t{video_id}\t{reason}", flush=True)
    print(f"Completed: {len(rows) - len(failed)}/{len(rows)}; failed: {len(failed)}", flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
