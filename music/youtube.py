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
        "🔎 جاري تحميل الصوت..."
    )



    try:


        os.makedirs(
            "downloads",
            exist_ok=True
        )



        options = {

            "format": "bestaudio/best",

            "outtmpl":
            "downloads/%(id)s.%(ext)s",

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




        with yt_dlp.YoutubeDL(options) as ydl:


            data = ydl.extract_info(
                f"ytsearch5:{query}",
                download=True
            )



            entries = data.get(
                "entries"
            )



            if not entries:

                await loading.edit_text(
                    "❌ لم أجد نتيجة"
                )

                return



            video = None


            for item in entries:

                if item:

                    video = item

                    break



            if not video:

                await loading.edit_text(
                    "❌ لم أجد مقطع مناسب"
                )

                return




            file_path = ydl.prepare_filename(
                video
            )



            title = video.get(
                "title",
                "صوت"
            )



            duration = video.get(
                "duration",
                0
            )



            if duration:

                minutes = duration // 60

                seconds = duration % 60

                time = f"{minutes}:{seconds:02d}"

            else:

                time = "غير معروف"




        caption = (
            f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {time}"
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

            audio=file_path,

            caption=caption,

            reply_markup=buttons

        )



        if os.path.exists(file_path):

            os.remove(file_path)



    except Exception as e:


        try:

            await loading.edit_text(
                f"❌ خطأ:\n{e}"
            )

        except:

            await update.message.reply_text(
                f"❌ خطأ:\n{e}"
            )