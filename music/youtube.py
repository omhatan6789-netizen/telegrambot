import os
import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ContextTypes
)


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



    msg = await update.message.reply_text(
        "🔎 جاري البحث وتحميل الصوت..."
    )



    try:

        os.makedirs(
            "downloads",
            exist_ok=True
        )



        ydl_opts = {

            # تحميل صوت فقط
            "format": "bestaudio/best",


            # تحويله mp3
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],


            "outtmpl":
            "downloads/%(title)s.%(ext)s",


            "noplaylist": True,


            # ملف الكوكيز
            "cookiefile":
            "./cookies.txt",


            "quiet": True,


            "no_warnings": True,

        }



        with yt_dlp.YoutubeDL(ydl_opts) as ydl:


            info = ydl.extract_info(
                f"ytsearch1:{query}",
                download=True
            )


            if not info.get("entries"):
                await msg.edit_text(
                    "❌ لم يتم العثور على المقطع"
                )
                return



            video = info["entries"][0]


            title = video.get(
                "title",
                "صوت"
            )


            duration = video.get(
                "duration_string",
                ""
            )


            file_path = (
                f"downloads/{title}.mp3"
            )



        if not os.path.exists(file_path):

            await msg.edit_text(
                "❌ لم يتم إنشاء الملف الصوتي"
            )
            return



        caption = (
            f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {duration}"
        )



        buttons = InlineKeyboardMarkup(
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

            caption=caption,

            reply_markup=buttons
        )



        os.remove(file_path)


        await msg.delete()



    except Exception as e:


        await msg.edit_text(
            f"❌ خطأ:\n{e}"
        )