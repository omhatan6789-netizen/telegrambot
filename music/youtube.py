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
            "❌ اكتب اسم البحث بعد بحث"
        )
        return



    msg = await update.message.reply_text(
        "🔎 جاري التحميل..."
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
            "cookiefile": "cookies.txt",
            "quiet": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }
            ]
        }



        with yt_dlp.YoutubeDL(ydl_opts) as ydl:


            result = ydl.extract_info(
                f"ytsearch1:{query}",
                download=True
            )


            if not result.get("entries"):

                await msg.edit_text(
                    "❌ لم أجد نتيجة"
                )
                return



            video = result["entries"][0]


            title = video.get(
                "title",
                "صوت"
            )


            duration = video.get(
                "duration",
                0
            )


            minutes = duration // 60
            seconds = duration % 60


            time = (
                f"{minutes}:{seconds:02d}"
                if duration
                else "غير معروف"
            )


            file_path = (
                f"downloads/{video['id']}.mp3"
            )



        if not os.path.exists(file_path):

            await msg.edit_text(
                "❌ فشل إنشاء الملف"
            )
            return



        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "• 𝑁𝐴𝑊𝐴𝐹 . ↠",
                        url=f"https://t.me/{BOT_USERNAME}"
                    )
                ]
            ]
        )



        await msg.delete()



        await update.message.reply_audio(

            audio=file_path,

            title=title,

            performer="𝑁𝐴𝑊𝐴𝐹",

            caption=f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {time}",

            reply_markup=keyboard

        )



        os.remove(file_path)



    except Exception as e:


        await msg.edit_text(
            f"❌ خطأ:\n{e}"
        )