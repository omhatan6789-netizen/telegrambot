import os
import glob
import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import ContextTypes


BOT_USERNAME = "lnll0bot"

CACHE_DIR = "youtube_cache"


async def youtube_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    text = update.message.text or ""


    if not text.startswith("بحث "):
        return


    query = text.replace(
        "بحث ",
        "",
        1
    ).strip()


    if not query:
        await update.message.reply_text(
            "❌ اكتب اسم البحث بعد كلمة بحث"
        )
        return



    await update.message.reply_text(
        "🔎 جاري البحث..."
    )


    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )


    try:


        ydl_opts = {

            "format":
            "bestaudio/best",


            "outtmpl":
            f"{CACHE_DIR}/%(id)s.%(ext)s",


            "noplaylist":
            True,


            "quiet":
            True,


            "no_warnings":
            True,


            "cookiefile":
            "./cookies.txt",


            "ffmpeg_location":
            "/usr/bin",


            "postprocessors":
            [
                {
                    "key":
                    "FFmpegExtractAudio",

                    "preferredcodec":
                    "mp3",

                    "preferredquality":
                    "192",
                }
            ]

        }



        with yt_dlp.YoutubeDL(ydl_opts) as ydl:


            search = ydl.extract_info(
                f"ytsearch5:{query}",
                download=False
            )


            entries = search.get(
                "entries",
                []
            )


            video = None


            for item in entries:

                if item:
                    video = item
                    break



            if not video:

                await update.message.reply_text(
                    "❌ لم يتم العثور على الأغنية"
                )
                return



            video_id = video.get(
                "id"
            )


            cached = glob.glob(
                f"{CACHE_DIR}/{video_id}.mp3"
            )


            if cached:

                file_path = cached[0]


            else:


                info = ydl.extract_info(
                    video["webpage_url"],
                    download=True
                )


                file_path = (
                    f"{CACHE_DIR}/{video_id}.mp3"
                )


            title = video.get(
                "title",
                "صوت"
            )


            duration = video.get(
                "duration",
                0
            )


        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "• 𝑁𝐴𝑊𝐴𝐹",
                        url=f"https://t.me/{BOT_USERNAME}"
                    )
                ]
            ]
        )


        await update.message.reply_audio(

            audio=open(
                file_path,
                "rb"
            ),

            title=title,

            duration=duration,

            caption=f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {duration//60}:{duration%60:02d}",

            reply_markup=keyboard
        )



    except Exception as e:

        await update.message.reply_text(
            f"❌ خطأ:\n{e}"
        )