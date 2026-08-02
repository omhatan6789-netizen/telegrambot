import os
import yt_dlp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


BOT_USERNAME = "@lnll0bot"


async def youtube_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text

    if not text.startswith("بحث "):
        return


    query = text.replace(
        "بحث ",
        "",
        1
    ).strip()


    if not query:

        await update.message.reply_text(
            "❌ اكتب اسم البحث"
        )

        return


    await update.message.reply_text(
        "🔎 جاري البحث..."
    )


    try:

        ydl_opts = {

            "format": "bestaudio/best",

            "outtmpl":
            "downloads/%(title)s.%(ext)s",

            "noplaylist": True,

            "quiet": True

        }


        os.makedirs(
            "downloads",
            exist_ok=True
        )


        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                f"ytsearch1:{query}",
                download=True
            )


            video = info["entries"][0]


            file_path = ydl.prepare_filename(video)


            title = video.get(
                "title",
                "صوت"
            )


            duration = video.get(
                "duration",
                0
            )


        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔵 فتح البوت",
                        url=f"https://t.me/{@lnll0bot}"
                    )
                ]
            ]
        )


        await update.message.reply_audio(

            audio=file_path,

            title=title,

            caption=(
                f"🎵 {title}\n"
                f"⏱ المدة: {duration} ثانية"
            ),

            reply_markup=buttons

        )


        os.remove(file_path)


    except Exception as e:


        await update.message.reply_text(
            f"❌ حصل خطأ:\n{e}"
        )