"""
Core Media Downloader Engine for MediaLink-Downloader.
Handles YouTube, Instagram (Reels, Posts, Photos, Carousels, Stories), TikTok, Twitter/X, and 1000+ sites.
Supports photos/images, videos, and MP3 audio extraction.
"""

import os
import re
import sys
import glob
import shutil
import logging
import urllib.parse
from typing import Dict, Any, List, Optional
import requests
import yt_dlp
import yt_dlp.extractor.instagram as ig

# Patch InstagramIE to prevent raising "There is no video in this post" on photo posts
_orig_raise_no_formats = ig.InstagramIE.raise_no_formats

def _safe_raise_no_formats(self, name='video', expected=False):
    if isinstance(name, str) and ("no video" in name.lower() or "no formats" in name.lower()):
        return
    _orig_raise_no_formats(self, name=name, expected=expected)

ig.InstagramIE.raise_no_formats = _safe_raise_no_formats

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


def clean_media_url(url: str) -> str:
    """Clean tracking and index parameters (e.g. ?img_index=3, ?igsh=...) from URLs."""
    try:
        parsed = urllib.parse.urlparse(url)
        if "instagram.com" in parsed.netloc:
            # Strip query parameters for Instagram posts/reels to prevent index errors
            path = parsed.path
            if not path.endswith("/"):
                path += "/"
            return f"{parsed.scheme}://{parsed.netloc}{path}"
    except Exception:
        pass
    return url


def is_supported_url(text: str) -> bool:
    """Check if the text contains a valid HTTP/HTTPS URL."""
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*'
    )
    return bool(url_pattern.search(text))


def extract_url(text: str) -> Optional[str]:
    """Extract the first URL from a given string and sanitize it."""
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*'
    )
    match = url_pattern.search(text)
    if not match:
        return None
    raw_url = match.group(0)
    return clean_media_url(raw_url)


def download_image_file(img_url: str, output_path: str) -> bool:
    """Download a single image from direct URL to disk."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.instagram.com/",
    }
    try:
        res = requests.get(img_url, headers=headers, timeout=30)
        if res.status_code == 200 and len(res.content) > 0:
            with open(output_path, "wb") as f:
                f.write(res.content)
            return True
    except Exception as e:
        logger.error(f"Failed to download image from {img_url}: {e}")
    return False


def get_best_thumbnail_url(thumbnails: List[Dict[str, Any]]) -> Optional[str]:
    """Find the highest resolution image URL from a list of thumbnails."""
    if not thumbnails:
        return None
    valid = [t for t in thumbnails if t.get("url")]
    if not valid:
        return None
    # Sort by dimension (width * height) descending
    sorted_thumbs = sorted(
        valid,
        key=lambda t: (t.get("width") or 0) * (t.get("height") or 0),
        reverse=True,
    )
    return sorted_thumbs[0].get("url")


def get_media_info(url: str) -> Dict[str, Any]:
    """Extract metadata for a URL without downloading."""
    clean_url = clean_media_url(url)
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
            info = ydl.extract_info(clean_url, download=False)
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


def _extract_images_from_info(info: Dict[str, Any], output_dir: str, title: str) -> List[Dict[str, Any]]:
    """Helper to extract photos/images from info dict or carousel entries."""
    files: List[Dict[str, Any]] = []
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title)[:60].strip() or "Instagram_Post"

    # Check if carousel / playlist of multiple entries
    entries = info.get("entries")
    if entries:
        for idx, entry in enumerate(entries, 1):
            if not entry:
                continue
            # If entry has formats (video), skip image extraction for that item
            if entry.get("formats"):
                continue
            thumbs = entry.get("thumbnails") or []
            best_url = get_best_thumbnail_url(thumbs) or entry.get("url")
            if best_url:
                filename = f"{clean_title}_slide_{idx}.jpg"
                fpath = os.path.join(output_dir, filename)
                if download_image_file(best_url, fpath):
                    files.append({
                        "path": fpath,
                        "filename": filename,
                        "size_bytes": os.path.getsize(fpath),
                        "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                        "media_type": "photo",
                    })
    else:
        # Single image post
        thumbs = info.get("thumbnails") or []
        best_url = get_best_thumbnail_url(thumbs) or info.get("url")
        if best_url:
            filename = f"{clean_title}.jpg"
            fpath = os.path.join(output_dir, filename)
            if download_image_file(best_url, fpath):
                files.append({
                    "path": fpath,
                    "filename": filename,
                    "size_bytes": os.path.getsize(fpath),
                    "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                    "media_type": "photo",
                })

    return files


def download_media(
    url: str,
    output_dir: str,
    format_type: str = "video",
    progress_hook = None,
) -> Dict[str, Any]:
    """
    Download media to output_dir.
    format_type: 'video' (MP4 video, or auto-fallback to photo for image posts)
                 'audio' (MP3 320kbps)
    Returns dictionary with status and downloaded file details.
    """
    os.makedirs(output_dir, exist_ok=True)
    clean_url = clean_media_url(url)
    ffmpeg_exe = get_ffmpeg_path()

    if not ffmpeg_exe:
        return {
            "success": False,
            "error": "FFmpeg executable not found. Install imageio-ffmpeg.",
        }

    # First, probe media info to determine whether it's video, audio, or photo
    probe_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "skip_download": True,
        "ffmpeg_location": ffmpeg_exe,
    }
    if has_valid_cookies():
        probe_opts["cookiefile"] = str(COOKIES_FILE_PATH)

    info = None
    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
    except Exception as probe_err:
        logger.info(f"Probe notice: {probe_err}")

    # Check if probe revealed an image-only post or photo carousel
    if info:
        title = info.get("title", "Media")
        extractor = info.get("extractor_key", "Generic")
        has_video_formats = bool(info.get("formats"))
        entries = info.get("entries")

        # If entries exist, check if ANY entry has video
        any_video_entry = False
        if entries:
            any_video_entry = any(bool(e and e.get("formats")) for e in entries)

        is_pure_image = not has_video_formats and not any_video_entry

        # If it's a photo post and user requested video / best quality
        if is_pure_image:
            if format_type == "audio":
                return {
                    "success": False,
                    "error": "This is a photo/image post with no audio tracks.",
                }

            logger.info("Detected image/photo post. Downloading high-resolution images...")
            photo_files = _extract_images_from_info(info, output_dir, title)
            if photo_files:
                return {
                    "success": True,
                    "title": title,
                    "extractor": extractor,
                    "media_type": "photo",
                    "files": photo_files,
                    "primary_file": photo_files[0],
                }

    # Standard video or audio download via yt-dlp
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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            dl_info = ydl.extract_info(clean_url, download=True)
            if not dl_info:
                return {"success": False, "error": "Failed to extract media."}

            title = dl_info.get("title", "Media")
            duration = dl_info.get("duration", 0)
            extractor = dl_info.get("extractor_key", "Generic")

            final_files: List[Dict[str, Any]] = []

            # Check requested downloads
            req_downloads = dl_info.get("requested_downloads")
            if req_downloads:
                for req in req_downloads:
                    fpath = req.get("filepath")
                    if fpath and os.path.isfile(fpath):
                        final_files.append({
                            "path": fpath,
                            "filename": os.path.basename(fpath),
                            "size_bytes": os.path.getsize(fpath),
                            "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                            "media_type": "video" if format_type == "video" else "audio",
                        })

            # Check entries
            if not final_files and "entries" in dl_info:
                for entry in dl_info["entries"]:
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
                                    "media_type": "video" if format_type == "video" else "audio",
                                })

            # Fallback search in output_dir
            if not final_files:
                target_ext = "mp4" if format_type == "video" else "mp3"
                media_id = dl_info.get("id", "")
                pattern = os.path.join(output_dir, f"*{media_id}*.{target_ext}")
                matching = glob.glob(pattern)
                if not matching:
                    matching = glob.glob(os.path.join(output_dir, f"*.{target_ext}"))

                for fpath in matching:
                    final_files.append({
                        "path": fpath,
                        "filename": os.path.basename(fpath),
                        "size_bytes": os.path.getsize(fpath),
                        "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                        "media_type": "video" if format_type == "video" else "audio",
                    })

            if not final_files:
                # If no video files, check if any photos were downloaded
                photos = glob.glob(os.path.join(output_dir, "*.jpg")) + glob.glob(os.path.join(output_dir, "*.webp"))
                if photos:
                    for p in photos:
                        final_files.append({
                            "path": p,
                            "filename": os.path.basename(p),
                            "size_bytes": os.path.getsize(p),
                            "size_mb": round(os.path.getsize(p) / (1024 * 1024), 2),
                            "media_type": "photo",
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
                "media_type": "video" if format_type == "video" else "audio",
                "files": final_files,
                "primary_file": final_files[0],
            }

    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e)
        # Handle "No video formats found" or "There is no video in this post" -> fallback to photo download
        if "no video formats found" in err_msg.lower() or "no video in this post" in err_msg.lower():
            logger.info("Caught image-only post. Attempting fallback photo extraction...")
            try:
                with yt_dlp.YoutubeDL(probe_opts) as ydl_fb:
                    fb_info = ydl_fb.extract_info(clean_url, download=False)
                    if fb_info:
                        fb_title = fb_info.get("title", "Instagram_Post")
                        photos = _extract_images_from_info(fb_info, output_dir, fb_title)
                        if photos:
                            return {
                                "success": True,
                                "title": fb_title,
                                "extractor": "Instagram",
                                "media_type": "photo",
                                "files": photos,
                                "primary_file": photos[0],
                            }
            except Exception as fb_err:
                logger.error(f"Fallback photo extraction error: {fb_err}")

        # Friendly hints for login or private content
        if "login" in err_msg.lower() or "private" in err_msg.lower():
            err_msg += (
                "\n\n[Tip] This content requires authentication. "
                "Add your Instagram cookies in 'cookies.txt'."
            )
        return {"success": False, "error": err_msg}

    except Exception as e:
        return {"success": False, "error": str(e)}
