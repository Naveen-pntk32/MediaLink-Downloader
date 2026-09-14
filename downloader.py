"""
Core Media Downloader Engine for MediaLink-Downloader.
Handles YouTube, Instagram (Reels, Posts, Stories, Carousels), TikTok, Twitter/X, and 1000+ sites.
Supports cookies for private Instagram accounts and restricted content.
"""

import os
import re
import sys
import glob
import shutil
import logging
from typing import Dict, Any, List, Optional
import yt_dlp

from config import COOKIES_FILE_PATH, has_valid_cookies

logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> Optional[str]:
    """Locate FFmpeg executable from imageio-ffmpeg or system PATH."""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe and os.path.isfile(ffmpeg_exe):
            return ffmpeg_exe
    except Exception:
        pass

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return None


def is_supported_url(text: str) -> bool:
    """Check if the text contains a valid HTTP/HTTPS URL."""
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*'
    )
    return bool(url_pattern.search(text))


def extract_url(text: str) -> Optional[str]:
    """Extract the first URL from a given string."""
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*'
    )
    match = url_pattern.search(text)
    return match.group(0) if match else None


def get_media_info(url: str) -> Dict[str, Any]:
    """
    Extract metadata for a URL without downloading.
    Returns title, duration, extractor, thumbnail, etc.
    """
    ffmpeg_exe = get_ffmpeg_path()
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "skip_download": True,
    }

    if ffmpeg_exe:
        ydl_opts["ffmpeg_location"] = ffmpeg_exe

    if has_valid_cookies():
        ydl_opts["cookiefile"] = str(COOKIES_FILE_PATH)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {"success": False, "error": "Could not retrieve media info."}

            title = info.get("title", "Media")
            duration = info.get("duration", 0)
            extractor = info.get("extractor_key", "Generic")
            thumbnail = info.get("thumbnail")
            is_playlist = "entries" in info

            return {
                "success": True,
                "title": title,
                "duration": duration,
                "extractor": extractor,
                "thumbnail": thumbnail,
                "is_playlist": is_playlist,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def download_media(
    url: str,
    output_dir: str,
    format_type: str = "video",
    progress_hook = None,
) -> Dict[str, Any]:
    """
    Download media to output_dir.
    format_type: 'video' (MP4) or 'audio' (MP3 320kbps)
    Returns a dictionary containing download status and file details.
    """
    os.makedirs(output_dir, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_path()

    if not ffmpeg_exe:
        return {
            "success": False,
            "error": "FFmpeg executable not found. Install imageio-ffmpeg.",
        }

    # Restrict title length in template to avoid MAX_PATH issues on Windows
    outtmpl = os.path.join(output_dir, "%(title).80s [%(id)s].%(ext)s")

    downloaded_files: List[str] = []

    def internal_hook(d):
        if d.get("status") == "finished":
            filename = d.get("filename")
            if filename and filename not in downloaded_files:
                downloaded_files.append(filename)
        if progress_hook:
            progress_hook(d)

    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "ffmpeg_location": ffmpeg_exe,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "windowsfilenames": True,
        "progress_hooks": [internal_hook],
    }

    # Inject cookies for Instagram / restricted accounts if file exists
    if has_valid_cookies():
        ydl_opts["cookiefile"] = str(COOKIES_FILE_PATH)

    if format_type == "video":
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoRemuxer",
                    "preferedformat": "mp4",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
        })
    elif format_type == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
        })
    else:
        return {"success": False, "error": f"Unsupported format_type: {format_type}"}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return {"success": False, "error": "Failed to extract media."}

            title = info.get("title", "Media")
            duration = info.get("duration", 0)
            extractor = info.get("extractor_key", "Generic")

            # Collect downloaded files
            final_files: List[Dict[str, Any]] = []

            # Check requested_downloads or files in info
            req_downloads = info.get("requested_downloads")
            if req_downloads:
                for req in req_downloads:
                    fpath = req.get("filepath")
                    if fpath and os.path.isfile(fpath):
                        final_files.append({
                            "path": fpath,
                            "filename": os.path.basename(fpath),
                            "size_bytes": os.path.getsize(fpath),
                            "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                        })

            # Check entries if it was a multi-item / carousel post
            if not final_files and "entries" in info:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    e_downloads = entry.get("requested_downloads")
                    if e_downloads:
                        for req in e_downloads:
                            fpath = req.get("filepath")
                            if fpath and os.path.isfile(fpath):
                                final_files.append({
                                    "path": fpath,
                                    "filename": os.path.basename(fpath),
                                    "size_bytes": os.path.getsize(fpath),
                                    "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                                })

            # Fallback: check downloaded_files hook records or output_dir search
            if not final_files:
                target_ext = "mp4" if format_type == "video" else "mp3"
                # Find matching files created recently in output_dir
                media_id = info.get("id", "")
                pattern = os.path.join(output_dir, f"*{media_id}*.{target_ext}")
                matching = glob.glob(pattern)
                if not matching:
                    pattern = os.path.join(output_dir, f"*.{target_ext}")
                    matching = glob.glob(pattern)

                for fpath in matching:
                    final_files.append({
                        "path": fpath,
                        "filename": os.path.basename(fpath),
                        "size_bytes": os.path.getsize(fpath),
                        "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                    })

            if not final_files:
                return {
                    "success": False,
                    "error": "Download completed, but could not locate the output file.",
                }

            return {
                "success": True,
                "title": title,
                "duration": duration,
                "extractor": extractor,
                "files": final_files,
                "primary_file": final_files[0],
            }

    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e)
        # Give friendly hints for private or login-required content
        if "login" in err_msg.lower() or "private" in err_msg.lower():
            err_msg += (
                "\n\n[Tip] This appears to be private or login-restricted content. "
                "Export cookies from an authorized browser account and place them as 'cookies.txt'."
            )
        return {"success": False, "error": err_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
