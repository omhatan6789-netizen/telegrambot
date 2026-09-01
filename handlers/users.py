from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database import connect


# ==================================================
# أمر ايدي
# ==================================================

async def user_id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message or not update.effective_user:
        return

    user = update.effective_user

    # --------------------------------------------------
    # جلب بيانات المستخدم
    # --------------------------------------------------

    conn = connect()
    cur = conn.cursor()

    try:

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

            joined_date = datetime.now().strftime("%Y/%m/%d")

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
                ON CONFLICT (user_id) DO NOTHING
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

    finally:

        cur.close()
        conn.close()

    # --------------------------------------------------
    # اسم المستخدم
    # --------------------------------------------------

    username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )

    # --------------------------------------------------
    # البايو
    # --------------------------------------------------

    bio = "لا يوجد"

    try:

        user_info = await context.bot.get_chat(user.id)

        if user_info.bio:
            bio = user_info.bio

    except Exception:
        pass

    # --------------------------------------------------
    # النص
    # --------------------------------------------------

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

    # --------------------------------------------------
    # صورة العضو
    # --------------------------------------------------

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

    except Exception:
        pass

    # --------------------------------------------------
    # بدون صورة
    # --------------------------------------------------

    await update.message.reply_text(text)


# ==================================================
# حفظ تاريخ دخول العضو
# ==================================================

async def save_join_date(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.chat_member:
        return

    member = update.chat_member
    new_member = member.new_chat_member

    if new_member.status not in (
        "member",
        "administrator"
    ):
        return

    user = new_member.user

    joined_date = datetime.now().strftime("%Y/%m/%d")

    conn = connect()
    cur = conn.cursor()

    try:

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
            ON CONFLICT (user_id) DO NOTHING
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

    finally:

        cur.close()
        conn.close()


# ==================================================
# حفظ رسائل المستخدم
# ==================================================

async def save_user_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # --------------------------------------------------
    # تجاهل أي شيء ليس رسالة
    # --------------------------------------------------

    if not update.message:
        return

    # --------------------------------------------------
    # القروبات فقط
    # --------------------------------------------------

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    user = update.effective_user

    if not user:
        return

    # --------------------------------------------------
    # اتصال قاعدة البيانات
    # --------------------------------------------------

    conn = connect()
    cur = conn.cursor()

    try:

        # --------------------------------------------------
        # تحديث المستخدم الموجود
        # --------------------------------------------------

        cur.execute(
            """
            UPDATE users
            SET
                messages = COALESCE(messages, 0) + 1,
                username = ?,
                first_name = ?
            WHERE user_id=?
            """,
            (
                user.username,
                user.first_name,
                user.id
            )
        )

        # --------------------------------------------------
        # المستخدم غير موجود
        # --------------------------------------------------

        if cur.rowcount == 0:

            # ----------------------------------------------
            # محاولة أخذ الرتبة المحفوظة
            # ----------------------------------------------

            cur.execute(
                """
                SELECT rank
                FROM ranks
                WHERE user_id=?
                """,
                (user.id,)
            )

            rank_data = cur.fetchone()

            if rank_data and rank_data[0]:
                rank = rank_data[0]
            else:
                rank = "عضو"

            # ----------------------------------------------
            # إنشاء المستخدم
            # ----------------------------------------------

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
                ON CONFLICT (user_id) DO UPDATE SET
                    messages = users.messages + 1,
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                """,
                (
                    user.id,
                    user.username,
                    user.first_name,
                    1,
                    rank,
                    datetime.now().strftime("%Y/%m/%d")
                )
            )

        # --------------------------------------------------
        # حفظ التغيير
        # --------------------------------------------------

        conn.commit()

    except Exception:

        conn.rollback()

    finally:

        cur.close()
        conn.close()