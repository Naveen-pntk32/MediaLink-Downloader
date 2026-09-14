"""
YouTube & Media Downloader & Local File Converter
Supports highest quality MP4 video or 320kbps MP3 audio extraction
from web URLs (YouTube, etc.) or local video/audio files from your PC.
"""

import os
import sys
import shutil
import subprocess
import colorama
from colorama import Fore, Style

# Force UTF-8 on Windows terminal to prevent charmap/cp1252 encoding errors
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Initialize colorama for Windows terminal support
colorama.init(autoreset=True)

import yt_dlp

# Default download folder: 'C:\Downloads'
DOWNLOAD_DIR = r"C:\Downloads"


def get_ffmpeg_path():
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


def print_banner():
    """Display an attractive terminal banner."""
    print(Fore.CYAN + "=" * 68)
    print(Fore.YELLOW + Style.BRIGHT + "       >> MEDIALINK DOWNLOADER & CONVERTER (MP4 & MP3) <<")
    print(Fore.CYAN + "=" * 68)
    print(Fore.WHITE + " Paste an Instagram, YouTube, or web link OR drag & drop a local file.")
    print(Fore.LIGHTBLACK_EX + f" Output folder: {DOWNLOAD_DIR}")
    print(Fore.CYAN + "-" * 68 + "\n")


def progress_hook(d):
    """Custom progress display during download."""
    status = d.get("status")
    if status == "downloading":
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        speed = d.get("speed") or 0
        eta = d.get("eta")

        # Format percentage
        if total > 0:
            percent = (downloaded / total) * 100
            percent_str = f"{percent:5.1f}%"
        else:
            percent_str = "  N/A%"

        # Format speed
        if speed > 1024 * 1024:
            speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
        elif speed > 1024:
            speed_str = f"{speed / 1024:.2f} KB/s"
        else:
            speed_str = f"{speed:.0f} B/s"

        eta_str = f"ETA: {eta}s" if eta is not None else "ETA: --"
        filename = os.path.basename(d.get("filename", "download"))
        if len(filename) > 30:
            filename = filename[:27] + "..."

        sys.stdout.write(
            f"\r{Fore.BLUE}[v] Downloading: {Fore.GREEN}{percent_str} "
            f"{Fore.WHITE}[{speed_str} | {eta_str}] {Fore.LIGHTBLACK_EX}{filename:<30}"
        )
        sys.stdout.flush()

    elif status == "finished":
        sys.stdout.write(f"\r{Fore.GREEN}[*] Download finished! Merging/converting media...{' ' * 25}\n")
        sys.stdout.flush()


def download_media(url: str, mode: str) -> bool:
    """
    Download and convert media from a web URL:
    mode '1': MP4 (Highest Quality Video + Audio)
    mode '2': MP3 (Highest Quality Audio 320kbps)
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_path()

    if not ffmpeg_exe:
        print(Fore.RED + "[!] Error: FFmpeg not found! Please run `pip install imageio-ffmpeg`.")
        return False

    outtmpl = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "ffmpeg_location": ffmpeg_exe,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "windowsfilenames": True,
    }

    cookies_path = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.isfile(cookies_path) and os.path.getsize(cookies_path) > 0:
        ydl_opts["cookiefile"] = cookies_path

    if mode == "1":
        print(Fore.CYAN + "\n[+] Setting up for Highest Quality MP4 (Video + Audio)...")
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoRemuxer",
                    "preferedformat": "mp4",
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                }
            ],
        })
    elif mode == "2":
        print(Fore.CYAN + "\n[+] Setting up for Highest Quality MP3 (320kbps Audio)...")
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
                }
            ],
        })
    else:
        print(Fore.RED + "[!] Invalid option selected.")
        return False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(Fore.YELLOW + "[*] Fetching media info & starting download...")
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Media")
            ext = "mp4" if mode == "1" else "mp3"

            print(Fore.GREEN + Style.BRIGHT + "\n[SUCCESS] Completed successfully!")
            print(Fore.WHITE + f"   Title   : {Fore.YELLOW}{title}")
            print(Fore.WHITE + f"   Format  : {Fore.CYAN}{ext.upper()}")
            print(Fore.WHITE + f"   Folder  : {Fore.LIGHTGREEN_EX}{DOWNLOAD_DIR}\n")
            return True

    except yt_dlp.utils.DownloadError as e:
        print(Fore.RED + f"\n[!] Download error: {e}")
        return False
    except Exception as e:
        print(Fore.RED + f"\n[!] Unexpected error: {e}")
        return False


def convert_local_media(file_path: str, mode: str) -> bool:
    """
    Convert an existing local video/audio file on the PC:
    mode '1': Convert to MP4 (High Quality H.264 + AAC)
    mode '2': Convert to MP3 (High Quality 320kbps Audio)
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ffmpeg_exe = get_ffmpeg_path()

    if not ffmpeg_exe:
        print(Fore.RED + "[!] Error: FFmpeg not found! Please run `pip install imageio-ffmpeg`.")
        return False

    if not os.path.isfile(file_path):
        print(Fore.RED + f"[!] File not found: {file_path}")
        return False

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    target_ext = "mp4" if mode == "1" else "mp3"
    target_filename = f"{base_name}.{target_ext}"
    target_path = os.path.join(DOWNLOAD_DIR, target_filename)

    # Avoid overwriting original if input is already the same as target
    if os.path.abspath(file_path) == os.path.abspath(target_path):
        target_filename = f"{base_name}_converted.{target_ext}"
        target_path = os.path.join(DOWNLOAD_DIR, target_filename)

    print(Fore.CYAN + f"\n[*] Source file: {os.path.basename(file_path)}")

    if mode == "1":
        print(Fore.CYAN + "[+] Converting local file to MP4 (High Quality)...")
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", file_path,
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            target_path
        ]
    elif mode == "2":
        print(Fore.CYAN + "[+] Extracting & Converting local file to MP3 (320kbps)...")
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", file_path,
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            target_path
        ]
    else:
        print(Fore.RED + "[!] Invalid option selected.")
        return False

    try:
        print(Fore.YELLOW + "[*] Processing with FFmpeg, please wait...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            print(Fore.RED + f"[!] Conversion failed:\n{result.stderr[-400:]}")
            return False

        file_size_mb = os.path.getsize(target_path) / (1024 * 1024)
        print(Fore.GREEN + Style.BRIGHT + "\n[SUCCESS] Local file converted successfully!")
        print(Fore.WHITE + f"   File    : {Fore.YELLOW}{target_filename}")
        print(Fore.WHITE + f"   Format  : {Fore.CYAN}{target_ext.upper()}")
        print(Fore.WHITE + f"   Size    : {Fore.CYAN}{file_size_mb:.2f} MB")
        print(Fore.WHITE + f"   Saved to: {Fore.LIGHTGREEN_EX}{target_path}\n")
        return True

    except Exception as e:
        print(Fore.RED + f"[!] Conversion error: {e}")
        return False


def prompt_format_choice() -> str:
    """Prompt user to choose between MP4 and MP3."""
    print(Fore.MAGENTA + Style.BRIGHT + "\nChoose output format:")
    print(f"  {Fore.CYAN}[1] {Fore.WHITE}Convert to {Fore.GREEN}MP4 {Fore.LIGHTBLACK_EX}(Highest Quality Video + Audio)")
    print(f"  {Fore.CYAN}[2] {Fore.WHITE}Convert to {Fore.YELLOW}MP3 {Fore.LIGHTBLACK_EX}(Highest Quality 320kbps Audio)")
    print(f"  {Fore.CYAN}[q] {Fore.LIGHTRED_EX}Cancel / Back")
    
    while True:
        choice = input(Fore.YELLOW + "\nEnter option (1 or 2, or 'q' to cancel): ").strip()
        if choice in ["1", "2", "q", "Q"]:
            return choice.lower()
        print(Fore.RED + "Invalid choice! Please enter 1, 2, or q.")


def open_download_folder():
    """Open the downloads folder in Windows Explorer."""
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.startfile(DOWNLOAD_DIR)
    except Exception as e:
        print(Fore.RED + f"Could not open directory: {e}")


def handle_input(raw_input_str: str) -> None:
    """Determine whether input is a web URL or a local file and process it."""
    # Strip quotes added by Windows drag & drop or copying
    target = raw_input_str.strip().strip('"').strip("'")

    if not target:
        return

    # Check if it's a local file
    if os.path.isfile(target):
        print(Fore.GREEN + f"\n[+] Local file detected: {os.path.basename(target)}")
        choice = prompt_format_choice()
        if choice != "q":
            convert_local_media(target, choice)
        else:
            print(Fore.LIGHTBLACK_EX + "Cancelled.\n")
        return

    # Check if it's a web URL
    if target.startswith("http://") or target.startswith("https://"):
        print(Fore.GREEN + f"\n[+] Web link detected!")
        choice = prompt_format_choice()
        if choice != "q":
            download_media(target, choice)
        else:
            print(Fore.LIGHTBLACK_EX + "Cancelled.\n")
        return

    print(Fore.RED + "[!] Invalid input! Please enter a valid URL (http/https) OR drag & drop a local file.\n")


def interactive_loop():
    """Main terminal loop."""
    print_banner()

    while True:
        try:
            user_input = input(
                Fore.GREEN + Style.BRIGHT + "Input> " +
                Fore.WHITE + "Paste URL or drag & drop file here (or 'q' to quit, 'o' to open downloads): " +
                Style.RESET_ALL
            ).strip()
            
            if not user_input:
                continue

            if user_input.lower() in ["q", "quit", "exit"]:
                print(Fore.YELLOW + "\nGoodbye! Exiting.")
                break

            if user_input.lower() in ["o", "open"]:
                open_download_folder()
                print(Fore.GREEN + "[*] Opened downloads folder.\n")
                continue

            handle_input(user_input)
            print(Fore.CYAN + "-" * 68 + "\n")

        except (KeyboardInterrupt, EOFError):
            print(Fore.YELLOW + "\n\nOperation cancelled. Goodbye!")
            break


def main():
    # If URL or file is supplied as command-line argument, handle it directly
    if len(sys.argv) > 1:
        print_banner()
        arg_input = sys.argv[1].strip()
        handle_input(arg_input)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
