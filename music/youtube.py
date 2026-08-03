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



    loading = await update.message.reply_text(
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
            "ignoreerrors": True,
            "socket_timeout": 30,
            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "android"
                    ]
                }
            }
        }

        "nocheckcertificate": True,

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Linux; Android 10; K) "
                "AppleWebKit/537.36 "
                "Chrome/120 Mobile Safari/537.36"
            )
        }
      



        with yt_dlp.YoutubeDL(options) as ydl:


        data = ydl.extract_info(
            f"ytsearch5:{query}",
            download=True
        )

        entries = data.get("entries")

        if not entries:
            await update.message.reply_text(
                "❌ لم أجد نتيجة للبحث"
            )
            return

        video = entries[0]


            file_path = ydl.prepare_filename(
                video
            )


            duration = video.get(
                "duration",
                0
            )


            minutes = duration // 60

            seconds = duration % 60


            time_text = (
                f"{minutes}:{seconds:02d}"
            )



        caption = (
            f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {time_text}"
        )



        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "بوت نواف واميره",
                        url=f"https://t.me/{BOT_USERNAME}"
                    )
                ]
            ]
        )



        await loading.delete()



        await update.message.reply_audio(

            audio=open(
                file_path,
                "rb"
            ),

            caption=caption,

            reply_markup=buttons

        )



        os.remove(
            file_path
        )



    except Exception as e:


        try:
            await loading.delete()
        except:
            pass


        await update.message.reply_text(
            f"❌ خطأ:\n{e}"
        )