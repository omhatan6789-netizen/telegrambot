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
            "❌ اكتب اسم الأغنية بعد بحث"
        )
        return



    msg = await update.message.reply_text(
        "🔎 جاري البحث وتحميل الأغنية..."
    )



    try:

        os.makedirs(
            "downloads",
            exist_ok=True
        )


        ydl_opts = {

            "format": "bestaudio/best",

            "outtmpl":
            "downloads/%(id)s.%(ext)s",

            "noplaylist": True,

            "quiet": True,

            "no_warnings": True,

            "cookiefile":
            "./cookies.txt",

            "ffmpeg_location":
            "/usr/bin",


            "postprocessors": [
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
                f"ytsearch10:{query}",
                download=False
            )


            entries = search.get(
                "entries",
                []
            )


            video = None


            for item in entries:

                if item and item.get("webpage_url"):
                    video = item
                    break



            if not video:

                await msg.edit_text(
                    "❌ لم أجد أغنية متاحة"
                )
                return



            info = ydl.extract_info(
                video["webpage_url"],
                download=True
            )



            title = info.get(
                "title",
                "صوت"
            )


            duration = info.get(
                "duration",
                0
            )



        files = glob.glob(
            "downloads/*.mp3"
        )


        if not files:

            await msg.edit_text(
                "❌ لم يتم إنشاء الملف"
            )
            return



        file_path = max(
            files,
            key=os.path.getmtime
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



        caption = (
            f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {duration // 60}:{duration % 60:02d}"
        )



        await update.message.reply_audio(

            audio=open(
                file_path,
                "rb"
            ),

            title=title,

            duration=duration,

            caption=caption,

            reply_markup=keyboard
        )



        os.remove(
            file_path
        )


        await msg.delete()



    except Exception as e:

        await msg.edit_text(
            f"❌ خطأ:\n{e}"
        )