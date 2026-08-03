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
            "❌ اكتب اسم البحث بعد كلمة بحث"
        )
        return



    msg = await update.message.reply_text(
        "🔎 جاري البحث..."
    )



    try:

        os.makedirs(
            "downloads",
            exist_ok=True
        )


        search = f"{query} audio"



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

        }



        with yt_dlp.YoutubeDL(ydl_opts) as ydl:


            info = ydl.extract_info(
                f"ytsearch5:{search}",
                download=True
            )



            entries = info.get(
                "entries",
                []
            )


            if not entries:

                await msg.edit_text(
                    "❌ لم يتم العثور على الأغنية"
                )

                return



            video = entries[0]



            title = video.get(
                "title",
                "صوت"
            )


            duration = video.get(
                "duration_string",
                ""
            )



        files = glob.glob(
            "downloads/*"
        )


        if not files:

            await msg.edit_text(
                "❌ فشل تحميل الملف"
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
            f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {duration}"
        )



        await update.message.reply_audio(
            audio=open(
                file_path,
                "rb"
            ),

            title=title,

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