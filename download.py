import os
import re
import uuid
import threading
import time
from typing import Dict, Any, Optional, List

from yt_dlp import YoutubeDL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_ROOT = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# job_id -> job dict
_JOBS: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def get_download_root() -> str:
    return DOWNLOAD_ROOT


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    text = text.strip("_")
    return text or "item"


def quality_format(file_type: str, quality: str) -> str:
    """
    Map (file_type, quality) to a yt-dlp format string.
    file_type: "mp4" | "mp3"
    quality: "high" | "medium" | "low"

    For MP4 we choose single-stream formats so we don't leave extra .m4a files.
    """
    file_type = (file_type or "mp4").lower()
    quality = (quality or "high").lower()

    if file_type == "mp3":
        # Audio only
        return "bestaudio/best"

    # MP4 video: progressive streams where possible (single file).
    if quality == "low":
        # Lowest quality MP4 if available, otherwise worst.
        return "worst[ext=mp4]/worst"
    if quality == "medium":
        # Up to 720p MP4, fallback to best MP4, then best.
        return "best[height<=720][ext=mp4]/best[ext=mp4]/best"
    # high
    return "best[ext=mp4]/best"


def get_playlist_info(url: str) -> Dict[str, Any]:
    """
    Return basic playlist info including thumbnail URLs.

    Shape:
    {
      "title": "...",
      "videos": [
        {"index": 1, "id": "VIDEO_ID", "title": "...", "thumbnail": "https://..."},
        ...
      ]
    }
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    videos: List[Dict[str, Any]] = []

    if info.get("_type") == "playlist":
        title = info.get("title") or "Playlist"
        entries = info.get("entries") or []
        for idx, e in enumerate(entries, start=1):
            if not e:
                continue
            vid = e.get("id")
            vtitle = e.get("title") or f"Video {idx}"
            thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None
            videos.append(
                {
                    "index": idx,
                    "id": vid,
                    "title": vtitle,
                    "thumbnail": thumb,
                }
            )
    else:
        title = info.get("title") or "Video"
        vid = info.get("id")
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None
        videos.append(
            {
                "index": 1,
                "id": vid,
                "title": title,
                "thumbnail": thumb,
            }
        )

    return {"title": title, "videos": videos}


def _run_download_job(job_id: str, playlist_url: str) -> None:
    """
    Execute the download job in a background thread.
    """
    with _jobs_lock:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["status"] = "running"
        client_id = job["client_id"]
        file_type = job["file_type"]
        quality = job["quality"]
        indices: List[int] = job.get("indices") or []

    client_dir = os.path.join(DOWNLOAD_ROOT, client_id)
    os.makedirs(client_dir, exist_ok=True)

    def progress_hook(d: Dict[str, Any]):
        info = d.get("info_dict") or {}
        playlist_index = info.get("playlist_index") or 0
        title = info.get("title") or f"Video {playlist_index or ''}".strip()

        with _jobs_lock:
            job_local = _JOBS.get(job_id)
            if not job_local:
                return

            videos = job_local.setdefault("videos", {})
            v = videos.setdefault(
                playlist_index,
                {
                    "index": playlist_index,
                    "title": title,
                    "progress": 0,
                    "status": "pending",
                    "filepath": None,
                },
            )

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                if total > 0:
                    percent = int(downloaded * 100 / total)
                else:
                    percent = 0
                v["progress"] = max(0, min(100, percent))
                v["status"] = "downloading"

            elif status == "finished":
                v["progress"] = 100
                v["status"] = "finished"
                filename = d.get("filename")
                if filename:
                    final_path = filename

                    # For MP3, yt-dlp downloads a source file and then creates .mp3.
                    # Point to the final .mp3 if it exists.
                    if file_type == "mp3":
                        base, _ = os.path.splitext(filename)
                        candidate = base + ".mp3"
                        if os.path.exists(candidate):
                            final_path = candidate

                    rel = os.path.relpath(final_path, DOWNLOAD_ROOT)
                    v["filepath"] = rel.replace(os.sep, "/")

    fmt = quality_format(file_type, quality)

    ydl_opts: Dict[str, Any] = {
        "outtmpl": os.path.join(
            client_dir, "%(playlist_title)s", "%(title)s.%(ext)s"
        ),
        "format": fmt,
        "noplaylist": False,
        "ignoreerrors": True,
        "quiet": True,
        "progress_hooks": [progress_hook],
    }

    if file_type == "mp3":
        # Extract audio to MP3; default behavior deletes original.
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    if indices:
        ydl_opts["playlist_items"] = ",".join(str(i) for i in indices)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=True)

        if info.get("_type") == "playlist":
            playlist_title: Optional[str] = info.get("title") or "Playlist"
        else:
            playlist_title = info.get("title") or "Video"

        with _jobs_lock:
            job2 = _JOBS.get(job_id)
            if job2:
                job2["playlist_title"] = playlist_title
                job2["status"] = "finished"
    except Exception as e:
        with _jobs_lock:
            job2 = _JOBS.get(job_id)
            if job2:
                job2["status"] = "error"
                job2["error"] = str(e)


def start_download_job(
    playlist_url: str,
    client_id: str,
    file_type: str,
    quality: str,
    indices: List[int],
) -> str:
    """
    Create a download job for a client and start it on a background thread.
    """
    file_type = (file_type or "mp4").lower()
    if file_type not in {"mp4", "mp3"}:
        file_type = "mp4"

    quality = (quality or "high").lower()
    if quality not in {"high", "medium", "low"}:
        quality = "high"

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _JOBS[job_id] = {
            "status": "pending",
            "playlist_title": None,
            "videos": {},
            "error": None,
            "client_id": client_id,
            "file_type": file_type,
            "quality": quality,
            "indices": sorted(set(indices)),
            "created_at": time.time(),
        }

    t = threading.Thread(
        target=_run_download_job, args=(job_id, playlist_url), daemon=True
    )
    t.start()
    return job_id


def get_job_progress(job_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """
    Get progress for a given job and client.
    """
    with _jobs_lock:
        job = _JOBS.get(job_id)
        if not job or job.get("client_id") != client_id:
            return None

        videos_dict = job.get("videos", {})
        videos_list = [videos_dict[idx] for idx in sorted(videos_dict.keys())]

        return {
            "status": job.get("status"),
            "playlist_title": job.get("playlist_title"),
            "videos": videos_list,
            "error": job.get("error"),
        }


def get_job_files(job_id: str, client_id: str) -> Optional[List[str]]:
    """
    Return a list of filepaths (relative to DOWNLOAD_ROOT) for finished videos in a job.
    """
    with _jobs_lock:
        job = _JOBS.get(job_id)
        if not job or job.get("client_id") != client_id:
            return None

        videos_dict = job.get("videos", {})
        paths: List[str] = []
        for v in videos_dict.values():
            p = v.get("filepath")
            if p:
                paths.append(p)
        return paths


def clear_client_jobs(client_id: str) -> None:
    """
    Remove all jobs associated with a client id.
    """
    with _jobs_lock:
        to_delete = [
            jid for jid, job in _JOBS.items() if job.get("client_id") == client_id
        ]
        for jid in to_delete:
            _JOBS.pop(jid, None)
