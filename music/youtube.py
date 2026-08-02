import os
import yt_dlp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


BOT_USERNAME = "lnll0bot"


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
            "❌ اكتب اسم البحث بعد كلمة بحث"
        )
        return



    await update.message.reply_text(
        "🔎 جاري البحث وتحميل الصوت..."
    )



    try:

        os.makedirs(
            "downloads",
            exist_ok=True
        )


        options = {
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "noplaylist": True,
            "quiet": True,
            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "android",
                        "web"
                    ]
                }
            }
        }



        with yt_dlp.YoutubeDL(options) as ydl:


            data = ydl.extract_info(
                f"ytsearch1:{query}",
                download=True
            )


            video = data["entries"][0]


            file_path = ydl.prepare_filename(
                video
            )


            title = video.get(
                "title",
                "صوت"
            )



        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔵 فتح البوت",
                        url=f"https://t.me/{BOT_USERNAME}"
                    )
                ]
            ]
        )


        await update.message.reply_audio(

            audio=file_path,

            title=title,

            caption=(
                f"🎵 {title}\n"
                "📥 تم التحميل من اليوتيوب"
            ),

            reply_markup=buttons

        )


        os.remove(file_path)



    except Exception as e:


        await update.message.reply_text(
            f"❌ خطأ:\n{e}"
        )