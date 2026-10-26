import os
import re
import glob
import uuid
import asyncio
import tempfile
from functools import partial

import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes


BOT_USERNAME = "lnll0bot"
SEARCH_RESULT_COUNT = 4
MAX_AUDIO_BYTES = 49 * 1024 * 1024

COOKIE_FILE = os.getenv("YOUTUBE_COOKIE_FILE", "cookies.txt")


def _youtube_options():
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreerrors": True,
    }

    if os.path.isfile(COOKIE_FILE):
        options["cookiefile"] = COOKIE_FILE

    return options


def _search_youtube(query):
    options = _youtube_options()
    options["extract_flat"] = True

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            f"ytsearch{SEARCH_RESULT_COUNT}:{query}",
            download=False,
        )

    return [
        {
            "id": item.get("id"),
            "title": item.get("title") or "مقطع بدون عنوان",
            "url": item.get("url")
            or f"https://www.youtube.com/watch?v={item.get('id')}",
            "duration": item.get("duration"),
        }
        for item in (info or {}).get("entries", [])
        if item and item.get("id")
    ]


def _download_audio(video_url, folder):
    options = _youtube_options()
    options.update({
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "outtmpl": os.path.join(folder, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "overwrites": True,
        "retries": 2,
        "fragment_retries": 2,
    })

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url, download=True)

    files = [
        path for path in glob.glob(os.path.join(folder, "*"))
        if os.path.isfile(path)
        and not path.endswith((".part", ".ytdl", ".json"))
    ]

    if not files:
        raise RuntimeError("لم يتم العثور على الملف بعد التحميل.")

    file_path = max(files, key=os.path.getmtime)

    if os.path.getsize(file_path) > MAX_AUDIO_BYTES:
        raise RuntimeError(
            "حجم الصوت أكبر من الحد المسموح لإرساله عبر البوت."
        )

    return file_path, info or {}


def _format_duration(seconds):
    if seconds is None:
        return ""

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


async def youtube_audio_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message or not message.text:
        return

    match = re.match(r"^(?:بحث|يوت)\s+(.+?)\s*$", message.text)

    if not match:
        return

    query = match.group(1).strip()

    if not query:
        await message.reply_text("❌ اكتب اسم المقطع بعد كلمة بحث.")
        return

    status = await message.reply_text("🔎 ثواني قاعد ابحث...")

    try:
        results = await asyncio.to_thread(_search_youtube, query)

        if not results:
            await status.edit_text("❌ لم يتم العثور على نتائج.")
            return

        search_id = uuid.uuid4().hex[:10]

        searches = context.chat_data.setdefault("youtube_searches", {})
        searches[search_id] = results

        keyboard = []

        for index, result in enumerate(results):
            title = result["title"]
            if len(title) > 55:
                title = title[:52] + "..."

            duration = _format_duration(result.get("duration"))
            label = f"{index + 1}. {title}"

            if duration:
                label += f" [{duration}]"

            keyboard.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"ytpick:{search_id}:{index}",
                )
            ])

        await status.edit_text(
            f"🎵 نتائج البحث عن: {query}\n\nاختر المقطع:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception:
        await status.edit_text(
            "❌ تعذّر البحث في يوتيوب.\n"
            "تأكد من تحديث yt-dlp وصحة ملف cookies.txt إن كنت تحتاجه."
        )


async def youtube_audio_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query or not query.data:
        return

    await query.answer()

    match = re.fullmatch(r"ytpick:([a-f0-9]+):(\d+)", query.data)

    if not match:
        return

    search_id = match.group(1)
    index = int(match.group(2))

    searches = context.chat_data.get("youtube_searches", {})
    results = searches.get(search_id, [])

    if index >= len(results):
        await query.answer("انتهت صلاحية النتائج، ابحث مرة ثانية.", show_alert=True)
        return

    video = results[index]
    chat_id = query.message.chat_id

    try:
        await query.message.delete()
    except Exception:
        pass

    status = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ جاري تحميل الصوت، انتظر...",
    )

    try:
        with tempfile.TemporaryDirectory(prefix="yt_audio_") as folder:
            file_path, info = await asyncio.to_thread(
                _download_audio,
                video["url"],
                folder,
            )

            title = info.get("title") or video["title"]
            duration = _format_duration(
                info.get("duration") or video.get("duration")
            )

            caption = "• Nawaf"
            if duration:
                caption += f" . ↠ {duration}"

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🌷",
                        url=f"https://t.me/{BOT_USERNAME}",
                    )
                ]
            ])

            with open(file_path, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=title[:64],
                    performer="Nawaf",
                    duration=int(info.get("duration") or video.get("duration") or 0),
                    caption=caption,
                    reply_markup=keyboard,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30,
                    pool_timeout=30,
                )

        await status.delete()

    except Exception:
        try:
            await status.edit_text(
                "❌ تعذّر تحميل هذا المقطع أو إرساله.\n"
                "جرّب اختيار نتيجة ثانية."
            )
        except Exception:
            pass

    finally:
        searches.pop(search_id, None)
