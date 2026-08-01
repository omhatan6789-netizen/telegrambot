from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database import connect


# ==========================
# أمر ايدي
# ==========================

async def user_id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT messages, rank, joined_date
        FROM users
        WHERE user_id=?
        """,
        (user.id,)
    )

    data = cur.fetchone()


    if data:

        messages = data[0] or 0
        rank = data[1] or "عضو"
        joined_date = data[2] or "غير معروف"


    else:

        joined_date = datetime.now().strftime(
            "%Y/%m/%d"
        )

        cur.execute(
            """
            INSERT INTO users
            (
                user_id,
                username,
                first_name,
                messages,
                rank,
                joined_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username,
                user.first_name,
                0,
                "عضو",
                joined_date
            )
        )

        conn.commit()

        messages = 0
        rank = "عضو"


    conn.close()


    username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )


    # جلب البايو
    try:
        user_info = await context.bot.get_chat(user.id)

        bio = user_info.bio or "لا يوجد"

    except:
        bio = "لا يوجد"



    text = f"""
🌷ᵂᴱᴸᶜᴼᴹᴱ ᵀᴼ ᴳᴿᴼᵁᴾ🌷

- عـيـونـي تـنـظـفـت يـوم شـفـت افـتـارك

🖱️ Name 𖦹 {user.first_name}
🖥️ USER 𖦹 {username}
💬 MSG 𖦹 {messages}
🛡 STA 𖦹 {rank}
ℹ️ ID 𖦹 {user.id}
🗒 BIO 𖦹 {bio}

📅 Joined Group 𖦹 {joined_date}
"""


    # جلب صورة العضو
    try:

        photos = await context.bot.get_user_profile_photos(
            user.id,
            limit=1
        )


        if photos.total_count > 0:

            photo = photos.photos[0][-1].file_id


            await update.message.reply_photo(
                photo=photo,
                caption=text
            )

            return


    except:
        pass


    # إذا ما فيه صورة
    await update.message.reply_text(text)



# ==========================
# حفظ تاريخ دخول العضو
# ==========================

async def save_join_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    member = update.chat_member

    new_member = member.new_chat_member


    if new_member.status not in [
        "member",
        "administrator"
    ]:
        return


    user = new_member.user


    joined_date = datetime.now().strftime(
        "%Y/%m/%d"
    )


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (
            user_id,
            username,
            first_name,
            messages,
            rank,
            joined_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user.id,
            user.username,
            user.first_name,
            0,
            "عضو",
            joined_date
        )
    )


    conn.commit()
    conn.close()


async def save_user_message(
    update,
    context
):

    # تجاهل أي شيء ليس رسالة
    if not update.message:
        return

    # القروبات فقط
    if update.effective_chat.type not in [
        "group",
        "supergroup"
    ]:
        return


    user = update.effective_user


    conn = connect()
    cur = conn.cursor()


    # زيادة عدد الرسائل
    cur.execute(
        """
        UPDATE users
        SET messages = messages + 1
        WHERE user_id=?
        """,
        (user.id,)
    )


    # إذا المستخدم غير موجود نضيفه
    if cur.rowcount == 0:

        cur.execute(
            """
            INSERT INTO users
            (
                user_id,
                username,
                first_name,
                messages,
                rank,
                joined_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username,
                user.first_name,
                1,
                "عضو",
                datetime.now().strftime("%Y/%m/%d")
            )
        )


    conn.commit()
    conn.close()    