import asyncio
import os
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


SEARCH_PREFIXES = ("بحث ", "يوت ")
MAX_AUDIO_BYTES = 49 * 1024 * 1024


def _download_first_youtube_result(query: str, folder: str):
    """Search YouTube and download the first result as an audio-compatible file."""
    with yt_dlp.YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "noplaylist": True,
    }) as ydl:
        search = ydl.extract_info(f"ytsearch1:{query}", download=False)
        entries = search.get("entries") or []
        if not entries:
            return None
        result = entries[0]
        video_id = result.get("id")
        webpage_url = (
            f"https://www.youtube.com/watch?v={video_id}"
            if video_id else result.get("url")
        )
        if not webpage_url:
            return None

    output_template = os.path.join(folder, "%(id)s.%(ext)s")
    with yt_dlp.YoutubeDL({
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "socket_timeout": 20,
        "retries": 2,
    }) as ydl:
        info = ydl.extract_info(webpage_url, download=True)
        filepath = Path(ydl.prepare_filename(info))

    if not filepath.exists():
        candidates = [p for p in Path(folder).glob("*") if p.is_file()]
        if not candidates:
            raise RuntimeError("Downloaded audio file was not found")
        filepath = candidates[0]

    return {
        "path": str(filepath),
        "title": info.get("title") or result.get("title") or query,
        "duration": int(info.get("duration") or result.get("duration") or 0),
    }


async def youtube_audio_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.text or not chat:
        return

    text = message.text.strip()
    query = None
    for prefix in SEARCH_PREFIXES:
        if text.startswith(prefix):
            query = text[len(prefix):].strip()
            break
    if query is None:
        return
    if not query:
        await message.reply_text("• اكتب اسم المقطع بعد بحث أو يوت.")
        return

    status = await message.reply_text("🔎 جاري البحث في يوتيوب وتحضير الصوت...")
    temp_dir = tempfile.mkdtemp(prefix="shanks_youtube_")
    try:
        result = await asyncio.to_thread(_download_first_youtube_result, query, temp_dir)
        if not result:
            await status.edit_text("ما لقيت نتائج مطابقة في يوتيوب.")
            return

        audio_path = Path(result["path"])
        if audio_path.stat().st_size > MAX_AUDIO_BYTES:
            await status.edit_text("حجم المقطع كبير جدًا لإرساله كصوت. جرّب مقطعًا أقصر.")
            return

        bot_user = await context.bot.get_me()
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🌹", url=f"https://t.me/{bot_user.username}?start=youtube_audio")
        ]])
        with audio_path.open("rb") as audio_file:
            await context.bot.send_audio(
                chat_id=chat.id,
                audio=audio_file,
                title=result["title"][:64],
                performer="Shanks",
                duration=result["duration"] or None,
                reply_to_message_id=message.message_id,
                reply_markup=keyboard,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=20,
                pool_timeout=20,
            )
        await status.delete()
    except Exception as exc:
        print(f"⚠️ YouTube audio error: {type(exc).__name__}: {exc}")
        try:
            await status.edit_text("تعذر تحميل الصوت الآن. جرّب البحث مرة ثانية بعد قليل.")
        except Exception:
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
