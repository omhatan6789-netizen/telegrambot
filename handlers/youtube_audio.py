import os
import re
import json
import uuid
import asyncio
import logging
import tempfile
import urllib.request
import urllib.error
import urllib.parse
import yt_dlp
import time
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

BOT_USERNAME = "lnll0bot"
SEARCH_RESULT_COUNT = 4
MAX_AUDIO_BYTES = 49 * 1024 * 1024

SAMPLECUT_API = "https://api.samplecut.app/v1/downloads"

def _youtube_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreerrors": True,
    }

def _get_youtube_api_keys():
    """
    استخراج جميع مفاتيح الـ API المتاحة من متغيرات البيئة.
    يدعم: YOUTUBE_API_KEY و YOUTUBE_API_KEY_2 وأي مفاتيح إضافية.
    """
    keys = []
    
    # جلب المفتاح الأساسي
    primary_key = os.getenv("YOUTUBE_API_KEY")
    if primary_key:
        keys.append(primary_key)
        
    # جلب المفاتيح الإضافية المترقمة (مثل YOUTUBE_API_KEY_2, YOUTUBE_API_KEY_3, ...)
    i = 2
    while True:
        key = os.getenv(f"YOUTUBE_API_KEY_{i}")
        if not key:
            break
        keys.append(key)
        i += 1
        
    return keys

def _search_youtube(query):
    api_keys = _get_youtube_api_keys()

    if not api_keys:
        raise RuntimeError(
            "لا توجد مفاتيح YOUTUBE_API_KEY معرفة في بيئة العمل (Render)."
        )

    last_exception = None

    # تجربة المفاتيح واحد تلو الآخر
    for index, api_key in enumerate(api_keys):
        params = urllib.parse.urlencode({
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": SEARCH_RESULT_COUNT,
            "regionCode": "SA",
            "relevanceLanguage": "ar",
            "key": api_key,
        })

        url = (
            "https://www.googleapis.com/youtube/v3/search?"
            + params
        )

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=15,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )
                
            # لو نجح الطلب، نقوم بمعالجة النتائج وإرجاعها فوراً
            results = []
            for item in data.get("items", []):
                video_id = item.get("id", {}).get("videoId")

                if not video_id:
                    continue

                snippet = item.get("snippet", {})

                results.append({
                    "id": video_id,
                    "title": snippet.get("title") or "مقطع بدون عنوان",
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "duration": None,
                })

            return results

        
        except urllib.error.HTTPError as exc:
            details = exc.read().decode(
                "utf-8",
                errors="replace",
            )

            try:
                error_data = json.loads(details)
                error_info = error_data.get("error", {})
                errors = error_info.get("errors", [])

                reasons = {
                    item.get("reason")
                    for item in errors
                    if item.get("reason")
                }

                status = error_info.get("status", "")
                message = error_info.get("message", "")

            except (ValueError, AttributeError):
                reasons = set()
                status = ""
                message = details

            logger.error(
                "YouTube API key #%d failed: HTTP %s, "
                "reasons=%s, status=%s, message=%s",
                index + 1,
                exc.code,
                sorted(reasons),
                status,
                message,
            )

            last_exception = exc

            quota_reasons = {
                "quotaExceeded",
                "dailyLimitExceeded",
            }

            if reasons & quota_reasons:
                logger.warning(
                    "نفدت حصة مفتاح البحث #%d؛ "
                    "سيتم تجربة المفتاح التالي.",
                    index + 1,
                )
                continue

            raise RuntimeError(
                f"YouTube API HTTP {exc.code}: "
                f"{', '.join(sorted(reasons)) or message}"
            ) from exc

    # لو خلصت كل المفاتيح وما زال فيه خطأ
    raise RuntimeError(
        "فشلت جميع مفاتيح YouTube API في إتمام البحث."
    ) from last_exception

def _download_audio(video_url, folder):
    """
    تحميل الصوت بواسطة Samplecut API بدل تنزيله مباشرة
    من يوتيوب باستخدام yt-dlp.
    """

    payload = json.dumps({
        "url": video_url,
        "format": "mp3",
        "response": "url",
    }).encode("utf-8")

    request = urllib.request.Request(
        SAMPLECUT_API,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Client-Name": "NawafTelegramBot",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            data = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")

        try:
            error_data = json.loads(error_body)
            api_error = error_data.get("error", {})
            error_code = api_error.get("code", "unknown")
            error_message = api_error.get("message", str(exc))
        except (ValueError, AttributeError):
            error_code = "http_error"
            error_message = error_body or str(exc)

        raise RuntimeError(
            f"Samplecut API error [{error_code}]: {error_message}"
        ) from exc

    download_url = data.get("download_url")

    if not download_url:
        raise RuntimeError(
            "Samplecut API لم تُرجع رابط تحميل الصوت."
        )

    file_path = os.path.join(folder, "audio.mp3")

    download_request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "NawafTelegramBot/1.0"},
    )

    try:
        with urllib.request.urlopen(
            download_request,
            timeout=120,
        ) as response:
            content_length = response.headers.get("Content-Length")

            if content_length:
                if int(content_length) > MAX_AUDIO_BYTES:
                    raise RuntimeError(
                        "حجم الصوت أكبر من الحد المسموح لإرساله."
                    )

            total_size = 0

            with open(file_path, "wb") as audio_file:
                while True:
                    chunk = response.read(64 * 1024)

                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > MAX_AUDIO_BYTES:
                        raise RuntimeError(
                            "حجم الصوت أكبر من الحد المسموح لإرساله."
                        )

                    audio_file.write(chunk)

    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        raise RuntimeError("ملف الصوت فارغ أو لم يكتمل تحميله.")

    info = {
        "title": data.get("title") or "صوت من يوتيوب",
        "duration": data.get("track_duration_sec"),
    }

    return file_path, info

def _format_duration(seconds):
    if seconds is None:
        return ""

    seconds = int(float(seconds))
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
        await message.reply_text(
            "❌ اكتب اسم المقطع بعد كلمة بحث."
        )
        return

    status = await message.reply_text("🔎 ثواني قاعد ابحث...")

    try:
        started = time.perf_counter()

        results = await asyncio.to_thread(
            _search_youtube,
            query,
        )

        logger.info(
            "YouTube search completed in %.2f seconds",
            time.perf_counter() - started,
        )

        if not results:
            await status.edit_text(
                "❌ لم يتم العثور على نتائج."
            )
            return

        search_id = uuid.uuid4().hex[:10]

        searches = context.chat_data.setdefault(
            "youtube_searches",
            {},
        )
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
        logger.exception("فشل البحث في يوتيوب")

        await status.edit_text(
            "❌ تعذّر البحث في يوتيوب.\n"
            "راجع سجلات Render لمعرفة السبب."
        )

async def youtube_audio_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query or not query.data:
        return

    match = re.fullmatch(
        r"ytpick:([a-f0-9]+):(\d+)",
        query.data,
    )

    if not match:
        await query.answer()
        return

    search_id = match.group(1)
    index = int(match.group(2))

    searches = context.chat_data.get("youtube_searches", {})
    results = searches.get(search_id, [])

    if index >= len(results):
        await query.answer(
            "انتهت صلاحية النتائج، ابحث مرة ثانية.",
            show_alert=True,
        )
        return

    await query.answer()

    video = results[index]
    chat_id = query.message.chat_id

    try:
        await query.message.delete()
    except Exception:
        pass

    status = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ قاعد ابحث، انتظر...",
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix="yt_audio_"
        ) as folder:
            file_path, info = await asyncio.to_thread(
                _download_audio,
                video["url"],
                folder,
            )

            title = info.get("title") or video["title"]

            duration_value = (
                info.get("duration")
                or video.get("duration")
                or 0
            )

            duration = _format_duration(duration_value)

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
                    duration=int(float(duration_value)),
                    caption=caption,
                    reply_markup=keyboard,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30,
                    pool_timeout=30,
                )

        await status.delete()

    except Exception:
        logger.exception(
            "فشل تحميل أو إرسال مقطع يوتيوب عبر Samplecut: %s",
            video.get("url"),
        )

        try:
            await status.edit_text(
                "❌ تعذّر تحميل هذا المقطع أو إرساله.\n"
                "جرّب اختيار نتيجة ثانية أو راجع سجلات Render."
            )
        except Exception:
            logger.exception(
                "تعذر تحديث رسالة حالة التحميل"
            )

    finally:
        searches.pop(search_id, None)
