"""
MediaLink-Downloader - Telegram Bot
Allows downloading media from Instagram (public & private), YouTube, TikTok, etc.
Provides interactive options to either 'Save to PC' or 'Send to Telegram Chat'.
"""

import os
import sys
import uuid
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import config
from downloader import (
    is_supported_url,
    extract_url,
    get_media_info,
    download_media,
    get_ffmpeg_path,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("MediaLinkBot")

# In-memory storage for pending user requests: {req_id: {"url": str, "chat_id": int, ...}}
pending_requests: Dict[str, Dict[str, Any]] = {}


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to satisfy cloud platform health checks (Render, Koyeb, etc.)."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"MediaLink-Downloader Bot is active and running 24/7!\n")

    def log_message(self, format, *args):
        pass  # Keep logs clean


def start_health_server(port: int):
    """Start the health check HTTP server on a background daemon thread."""
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Cloud health-check web server started on port {port}")


def check_authorized(update: Update) -> bool:
    """Check if the user is authorized based on ALLOWED_USER_IDS config."""
    if not config.ALLOWED_USER_IDS:
        return True
    user = update.effective_user
    if user and user.id in config.ALLOWED_USER_IDS:
        return True
    return False


async def unauthorized_reply(update: Update):
    """Reply when an unauthorized user attempts to use the bot."""
    user = update.effective_user
    user_id = user.id if user else "Unknown"
    await update.effective_message.reply_text(
        f"⛔ *Access Denied*\n\nYour Telegram User ID is `{user_id}`.\n"
        f"To use this bot, add your ID to `ALLOWED_USER_IDS` in the `.env` file on the host.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    if not check_authorized(update):
        await unauthorized_reply(update)
        return

    cookie_status = "✅ Active (`cookies.txt` loaded)" if config.has_valid_cookies() else "⚪ None (Public only)"
    ffmpeg_found = "✅ Available" if get_ffmpeg_path() else "❌ Missing FFmpeg"

    welcome_text = (
        "🚀 *Welcome to MediaLink Downloader Bot!*\n\n"
        "Send me any video or media link to get started:\n"
        "• *Instagram*: Reels, Posts, Stories, Carousels (Public & Private)\n"
        "• *YouTube*: Videos, Shorts, Music\n"
        "• *TikTok, Twitter/X, Facebook, Reddit, etc.*\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📁 *PC Download Folder*: `{config.PC_DOWNLOAD_DIR}`\n"
        f"🍪 *Cookies Status*: {cookie_status}\n"
        f"🎬 *FFmpeg*: {ffmpeg_found}\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 *Just paste any link below to begin!*"
    )
    await update.effective_message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command."""
    if not check_authorized(update):
        await unauthorized_reply(update)
        return

    help_text = (
        "📖 *MediaLink Downloader - Help Guide*\n\n"
        "*1. How to download?*\n"
        "• Copy any media link from Instagram, YouTube, etc.\n"
        "• Paste it in this chat.\n"
        "• Choose whether you want to save it to your PC or receive the file directly in this chat!\n\n"
        "*2. Instagram Private Accounts:*\n"
        "• You can download private account content *if* your Instagram account follows that person.\n"
        "• Export your cookies from your browser using the Chrome/Firefox extension *'Get cookies.txt LOCALLY'*.\n"
        "• Place the saved `cookies.txt` file into the bot's root folder.\n"
        "• The bot will immediately use it for private posts and stories!\n\n"
        "*3. Telegram File Limits:*\n"
        "• Standard Telegram Bots can upload files up to *50 MB* directly to chat.\n"
        "• For large files (>50MB), use *'Save to PC'*, or choose *'MP3 Audio'*.\n\n"
        "*Commands:*\n"
        "/start - Show welcome menu & status\n"
        "/status - Detailed system diagnostics\n"
        "/help - Show this guide"
    )
    await update.effective_message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /status command."""
    if not check_authorized(update):
        await unauthorized_reply(update)
        return

    ffmpeg_path = get_ffmpeg_path() or "Not found"
    
    # Check domains in cookies.txt
    cookie_domains = []
    if config.has_valid_cookies():
        try:
            with open(config.COOKIES_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    sline = line.strip()
                    if sline and not sline.startswith("#"):
                        parts = sline.split("\t")
                        if len(parts) >= 7:
                            cookie_domains.append(parts[0])
        except Exception:
            pass

    unique_domains = sorted(set(cookie_domains))
    if unique_domains:
        cookie_status = f"Active ({', '.join(unique_domains)})"
    elif config.has_valid_cookies():
        cookie_status = "Loaded"
    else:
        cookie_status = "Not found (public access only)"

    msg = (
        "📊 *System Diagnostics*\n\n"
        f"• *PC Destination*: `{config.PC_DOWNLOAD_DIR}`\n"
        f"• *Cookies Status*: `{cookie_status}`\n"
        f"• *FFmpeg Path*: `{ffmpeg_path}`\n"
        f"• *Temp Directory*: `{config.TEMP_DOWNLOAD_DIR}`\n\n"
        "💡 _Tip: You can send any exported `cookies.txt` file directly into this chat to update authentication!_"
    )
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detect URLs and prompt user with inline choice buttons."""
    if not check_authorized(update):
        await unauthorized_reply(update)
        return

    text = update.effective_message.text or ""
    url = extract_url(text)

    if not url:
        await update.effective_message.reply_text(
            "ℹ️ Please send a valid web link (e.g., Instagram Reel/Post, YouTube Video, TikTok, etc.)."
        )
        return

    # Generate request id
    req_id = str(uuid.uuid4())[:8]
    pending_requests[req_id] = {
        "url": url,
        "chat_id": update.effective_chat.id,
        "user_id": update.effective_user.id if update.effective_user else 0,
    }

    # Clean up old requests if dictionary exceeds 200 items
    if len(pending_requests) > 200:
        oldest = list(pending_requests.keys())[0]
        del pending_requests[oldest]

    # Detect platform name for display
    platform = "Media"
    if "instagram.com" in url:
        platform = "Instagram"
    elif "youtube.com" in url or "youtu.be" in url:
        platform = "YouTube"
    elif "tiktok.com" in url:
        platform = "TikTok"
    elif "twitter.com" in url or "x.com" in url:
        platform = "X / Twitter"
    elif "reddit.com" in url:
        platform = "Reddit"

    keyboard = [
        [
            InlineKeyboardButton("📥 Save to PC", callback_data=f"pc_video:{req_id}"),
            InlineKeyboardButton("📱 Send to Chat", callback_data=f"chat_video:{req_id}"),
        ],
        [
            InlineKeyboardButton("💾 Save MP3 to PC", callback_data=f"pc_audio:{req_id}"),
            InlineKeyboardButton("🎵 Send MP3 to Chat", callback_data=f"chat_audio:{req_id}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{req_id}"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        f"🎯 *{platform} Link Detected!*\n`{url}`\n\n"
        "Where would you like to receive or save the media?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from the inline keyboard."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if ":" not in data:
        return

    action, req_id = data.split(":", 1)

    if action == "cancel":
        if req_id in pending_requests:
            del pending_requests[req_id]
        await query.edit_message_text("❌ Request cancelled.")
        return

    req_data = pending_requests.get(req_id)
    if not req_data:
        await query.edit_message_text("⚠️ This request has expired. Please paste the link again.")
        return

    url = req_data["url"]
    chat_id = req_data["chat_id"]

    # Determine action settings
    save_to_pc = action.startswith("pc_")
    format_type = "audio" if action.endswith("_audio") else "video"

    target_label = f"PC ({config.PC_DOWNLOAD_DIR})" if save_to_pc else "Telegram Chat"
    format_label = "MP3 Audio (320kbps)" if format_type == "audio" else "Best Quality (Video / Photo)"

    await query.edit_message_text(
        f"⏳ *Processing...*\n"
        f"• *Destination*: {target_label}\n"
        f"• *Format*: {format_label}\n"
        f"• *Status*: Downloading media from web...",
        parse_mode=ParseMode.MARKDOWN,
    )

    output_dir = config.PC_DOWNLOAD_DIR if save_to_pc else str(config.TEMP_DOWNLOAD_DIR / req_id)

    # Run blocking download in thread pool
    try:
        result = await asyncio.to_thread(
            download_media,
            url=url,
            output_dir=output_dir,
            format_type=format_type,
        )
    except Exception as e:
        logger.error(f"Download exception: {e}", exc_info=True)
        result = {"success": False, "error": str(e)}

    if not result.get("success"):
        error_msg = result.get("error", "Unknown download error occurred.")
        if "only available for registered users who follow this account" in error_msg:
            error_msg += (
                "\n\n🔒 *Private Account Notice*:\n"
                "This post belongs to a private Instagram account.\n"
                "To download private posts, please send your exported Instagram `cookies.txt` file directly into this chat!"
            )
        elif "Sign in to confirm you're not a bot" in error_msg:
            error_msg += (
                "\n\n🤖 *YouTube Bot Block Notice*:\n"
                "YouTube is requiring login verification.\n"
                "Please export your YouTube `cookies.txt` file and send it directly into this chat!"
            )
        await query.edit_message_text(
            f"❌ *Download Failed*\n\n{error_msg}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    title = result.get("title", "Media")
    files = result.get("files", [])
    media_type = result.get("media_type", "video")

    # Case 1: Save to PC
    if save_to_pc:
        type_icon = "📸" if media_type == "photo" else ("🎵" if media_type == "audio" else "🎬")
        file_summary = "\n".join(
            [f"• `{f['filename']}` ({f['size_mb']} MB)" for f in files]
        )
        success_msg = (
            f"✅ *Saved to PC Successfully!*\n\n"
            f"{type_icon} *Title*: {title}\n"
            f"📁 *Folder*: `{config.PC_DOWNLOAD_DIR}`\n"
            f"📦 *Files* ({len(files)} item{'s' if len(files) > 1 else ''}):\n{file_summary}"
        )
        await query.edit_message_text(success_msg, parse_mode=ParseMode.MARKDOWN)
        pending_requests.pop(req_id, None)
        return

    # Case 2: Send to Telegram Chat
    await query.edit_message_text(
        f"📤 *Download finished! Sending to Telegram chat...*\n"
        f"🎬 *Title*: {title}",
        parse_mode=ParseMode.MARKDOWN,
    )

    # If carousel with multiple photos (up to 10), send as a single album
    all_photos = all(
        item.get("media_type") == "photo" or os.path.splitext(item["path"])[1].lower() in [".jpg", ".jpeg", ".png", ".webp"]
        for item in files
    )

    if len(files) > 1 and all_photos and len(files) <= 10:
        file_handles = []
        try:
            media_group = []
            for i, item in enumerate(files):
                fh = open(item["path"], "rb")
                file_handles.append(fh)
                caption = f"📸 {title[:100]} ({i+1}/{len(files)})" if i == 0 else None
                media_group.append(InputMediaPhoto(media=fh, caption=caption))
            await context.bot.send_media_group(chat_id=chat_id, media=media_group)
            for fh in file_handles:
                fh.close()
            for item in files:
                try:
                    if os.path.isfile(item["path"]):
                        os.remove(item["path"])
                except Exception:
                    pass
            pending_requests.pop(req_id, None)
            return
        except Exception as album_err:
            logger.warning(f"Failed to send as album, falling back to individual send: {album_err}")
            for fh in file_handles:
                try:
                    fh.close()
                except Exception:
                    pass

    for item in files:
        fpath = item["path"]
        size_mb = item["size_mb"]
        item_type = item.get("media_type")
        ext = os.path.splitext(fpath)[1].lower()
        is_photo = item_type == "photo" or ext in [".jpg", ".jpeg", ".png", ".webp"]
        is_audio = format_type == "audio" or ext in [".mp3", ".m4a", ".aac"]

        # Telegram standard Bot API upload limit is 50MB
        if size_mb > 50.0:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ File `{item['filename']}` is *{size_mb} MB*, which exceeds "
                    "Telegram's 50MB bot upload limit.\n"
                    f"👉 It has been moved to your PC folder: `{config.PC_DOWNLOAD_DIR}`"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            try:
                dest = os.path.join(config.PC_DOWNLOAD_DIR, item["filename"])
                os.replace(fpath, dest)
            except Exception as e:
                logger.warning(f"Failed to move file to PC folder: {e}")
            continue

        try:
            with open(fpath, "rb") as f:
                if is_audio:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        title=title[:60],
                        caption=f"🎵 {title[:100]}",
                    )
                elif is_photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=f,
                        caption=f"📸 {title[:100]}",
                    )
                else:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=f"🎬 {title[:100]}",
                        supports_streaming=True,
                    )
        except Exception as upload_err:
            logger.error(f"Error uploading file: {upload_err}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Failed to upload file to chat: {upload_err}",
            )
        finally:
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except Exception:
                pass

    # Clean up temp folder for this request
    try:
        if os.path.isdir(output_dir):
            os.rmdir(output_dir)
    except Exception:
        pass

    pending_requests.pop(req_id, None)

    try:
        await query.delete_message()
    except Exception:
        pass


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded cookie files (e.g. cookies.txt or instagram_cookies.txt)."""
    if not check_authorized(update):
        await unauthorized_reply(update)
        return

    doc = update.effective_message.document
    if not doc:
        return

    filename = (doc.file_name or "").lower()
    if not (filename.endswith(".txt") or "cookie" in filename):
        await update.effective_message.reply_text(
            "ℹ️ To upload cookies, please send a `.txt` file exported using 'Get cookies.txt LOCALLY'."
        )
        return

    status_msg = await update.effective_message.reply_text("📥 *Receiving cookies file...*", parse_mode=ParseMode.MARKDOWN)

    try:
        file = await context.bot.get_file(doc.file_id)
        temp_path = config.TEMP_DOWNLOAD_DIR / f"upload_{doc.file_id}.txt"
        await file.download_to_drive(custom_path=temp_path)

        with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
            new_content = f.read()

        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass

        if not ("#" in new_content or "TRUE" in new_content or "FALSE" in new_content or "\t" in new_content):
            await status_msg.edit_text("❌ The uploaded file does not appear to be a valid Netscape cookie file.")
            return

        new_lines = new_content.splitlines()
        clean_new_lines = []
        for line in new_lines:
            sline = line.strip()
            if not sline or sline.startswith("#"):
                continue
            parts = sline.split("\t")
            if len(parts) >= 7:
                cookie_name = parts[5]
                # Filter out volatile SIDTS
                if "SIDTS" in cookie_name:
                    continue
                clean_new_lines.append(sline)

        if not clean_new_lines:
            await status_msg.edit_text("❌ No valid cookie entries found in the file.")
            return

        # Load existing cookies from master
        existing_lines = []
        if config.COOKIES_FILE_PATH.exists():
            with open(config.COOKIES_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    sline = line.strip()
                    if sline and not sline.startswith("#"):
                        existing_lines.append(sline)

        # Merge by (domain, path, cookie_name)
        cookie_map = {}
        for line in existing_lines:
            parts = line.split("\t")
            if len(parts) >= 7:
                key = (parts[0], parts[2], parts[5])
                cookie_map[key] = line

        for line in clean_new_lines:
            parts = line.split("\t")
            key = (parts[0], parts[2], parts[5])
            cookie_map[key] = line

        with open(config.COOKIES_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n# Generated by MediaLink-Downloader\n\n")
            for line in cookie_map.values():
                f.write(line + "\n")

        all_domains = sorted(set(k[0] for k in cookie_map.keys()))
        domain_list = "\n".join([f"• `{d}`" for d in all_domains])

        await status_msg.edit_text(
            f"🍪 *Cookies Successfully Updated!*\n\n"
            f"📦 *Active Domains* ({len(all_domains)}):\n{domain_list}\n\n"
            f"🔢 *Total Active Cookies*: {len(cookie_map)}\n\n"
            f"✅ Authentication is now active for private Instagram accounts and YouTube!",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Error saving uploaded cookies: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Failed to process cookies file: {e}")


def main():
    """Start the Telegram Bot."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token or token == "your_bot_token_here":
        print("\n" + "=" * 68)
        print(" [!] ERROR: Telegram Bot Token is missing!")
        print("=" * 68)
        print(" 1. Open Telegram and search for @BotFather.")
        print(" 2. Send '/newbot' and follow instructions to get your HTTP API Token.")
        print(" 3. Create or open the '.env' file in this folder and set:")
        print("    TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
        print("=" * 68 + "\n")
        sys.exit(1)

    print("=" * 68)
    print("        >> MEDIALINK-DOWNLOADER TELEGRAM BOT STARTING <<")
    print("=" * 68)
    print(f" PC Download Folder : {config.PC_DOWNLOAD_DIR}")
    print(f" Cookies File       : {'Loaded (Active)' if config.has_valid_cookies() else 'None (Public only)'}")
    print(f" FFmpeg Status      : {'Found' if get_ffmpeg_path() else 'NOT FOUND'}")
    print("=" * 68)
    print(" Bot is polling for messages... Press Ctrl+C to stop.\n")

    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # If deployed on cloud platform (Render, Koyeb, etc.), start health-check web server
    port_env = os.getenv("PORT")
    if port_env and port_env.isdigit():
        start_health_server(int(port_env))

    # Run bot
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
