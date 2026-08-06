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
            "❌ اكتب اسم الأغنية بعد بحث"
        )
        return


    msg = await update.message.reply_text(
        "🔎 جاري البحث..."
    )


    try:

        os.makedirs(
            CACHE_DIR,
            exist_ok=True
        )


        ydl_opts = {

            "format": "bestaudio/best",

            "outtmpl":
            f"{CACHE_DIR}/%(id)s.%(ext)s",

            "noplaylist": True,

            "quiet": True,

            "no_warnings": True,

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


            videos = search.get(
                "entries",
                []
            )


            if not videos:

                await msg.edit_text(
                    "❌ لا توجد نتائج"
                )
                return



            file_path = None

            title = "صوت"

            duration = 0



            for video in videos:


                if not video:
                    continue


                try:

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


                        possible = glob.glob(
                            f"{CACHE_DIR}/{video_id}*"
                        )


                        mp3_files = [
                            x for x in possible
                            if x.endswith(".mp3")
                        ]


                        if mp3_files:

                            file_path = mp3_files[0]



                    if file_path and os.path.exists(file_path):

                        title = video.get(
                            "title",
                            "صوت"
                        )

                        duration = video.get(
                            "duration",
                            0
                        )

                        break



                except Exception:

                    continue



        if not file_path:

            await msg.edit_text(
                "❌ لم أجد أغنية قابلة للتحميل"
            )
            return



        minutes = duration // 60
        seconds = duration % 60


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

            caption=
            f"• 𝑁𝐴𝑊𝐴𝐹 . ↠ {minutes}:{seconds:02d}",

            reply_markup=keyboard
        )


        await msg.delete()



    except Exception as e:


        await msg.edit_text(
            f"❌ خطأ:\n{e}"
        )