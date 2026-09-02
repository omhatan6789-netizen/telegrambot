from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database import connect


# ==================================================
# Cache بيانات المستخدمين
# ==================================================

_user_cache = {}


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

    cached = _user_cache.get(user.id)

    if cached:

        messages = cached.get("messages", 0)
        rank = cached.get("rank", "عضو")
        joined_date = cached.get(
            "joined_date",
            "غير معروف"
        )

    else:

        conn = connect()

        try:

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
                    ON CONFLICT (user_id)
                    DO NOTHING
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

            # --------------------------------------------------
            # حفظ بالكاش
            # --------------------------------------------------

            _user_cache[user.id] = {
                "messages": messages,
                "rank": rank,
                "joined_date": joined_date,
            }

            try:
                cur.close()
            except Exception:
                pass

        finally:

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

        user_info = await context.bot.get_chat(
            user.id
        )

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

    await update.message.reply_text(
        text
    )


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

    joined_date = datetime.now().strftime(
        "%Y/%m/%d"
    )

    conn = connect()

    try:

        cur = conn.cursor()

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
            ON CONFLICT (user_id)
            DO NOTHING
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

        # --------------------------------------------------
        # تحديث الكاش
        # --------------------------------------------------

        _user_cache[user.id] = {
            "messages": 0,
            "rank": "عضو",
            "joined_date": joined_date,
        }

        try:
            cur.close()
        except Exception:
            pass

    finally:

        conn.close()


# ==================================================
# تجميع رسائل المستخدمين
# ==================================================

_pending_messages = {}
_pending_user_data = {}


# ==================================================
# الحد الأقصى قبل الحفظ
# ==================================================

MESSAGE_BATCH_SIZE = 10


# ==================================================
# حفظ الرسائل المتجمعة
# ==================================================

async def flush_user_messages():

    global _pending_messages
    global _pending_user_data

    if not _pending_messages:
        return

    # --------------------------------------------------
    # أخذ نسخة من الدفعة الحالية
    # --------------------------------------------------

    messages = _pending_messages
    user_data = _pending_user_data

    _pending_messages = {}
    _pending_user_data = {}

    conn = connect()

    try:

        cur = conn.cursor()

        # ==================================================
        # حفظ جميع المستخدمين
        # ==================================================

        for user_id, count in messages.items():

            data = user_data.get(user_id)

            if not data:
                continue

            username, first_name = data

            # --------------------------------------------------
            # تحديث المستخدم الموجود
            # --------------------------------------------------

            cur.execute(
                """
                UPDATE users
                SET
                    messages = COALESCE(messages, 0) + ?,
                    username = ?,
                    first_name = ?
                WHERE user_id=?
                """,
                (
                    count,
                    username,
                    first_name,
                    user_id
                )
            )

            # --------------------------------------------------
            # إذا المستخدم غير موجود
            # --------------------------------------------------

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
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        messages =
                            COALESCE(users.messages, 0)
                            + EXCLUDED.messages,

                        username =
                            EXCLUDED.username,

                        first_name =
                            EXCLUDED.first_name
                    """,
                    (
                        user_id,
                        username,
                        first_name,
                        count,
                        "عضو",
                        datetime.now().strftime(
                            "%Y/%m/%d"
                        )
                    )
                )

        conn.commit()

        # ==================================================
        # تحديث الكاش
        # ==================================================

        for user_id, count in messages.items():

            data = user_data.get(user_id)

            if not data:
                continue

            cached = _user_cache.get(user_id)

            if cached:

                cached["messages"] = (
                    cached.get("messages", 0)
                    + count
                )

                cached["username"] = data[0]
                cached["first_name"] = data[1]

            else:

                _user_cache[user_id] = {
                    "messages": count,
                    "rank": "عضو",
                    "joined_date":
                        datetime.now().strftime(
                            "%Y/%m/%d"
                        ),
                    "username": data[0],
                    "first_name": data[1],
                }

        try:
            cur.close()
        except Exception:
            pass

    except Exception as e:

        try:
            conn.rollback()
        except Exception:
            pass

        # --------------------------------------------------
        # نرجع الرسائل للذاكرة
        # --------------------------------------------------

        for user_id, count in messages.items():

            _pending_messages[user_id] = (
                _pending_messages.get(
                    user_id,
                    0
                )
                + count
            )

            if user_id in user_data:

                _pending_user_data[user_id] = (
                    user_data[user_id]
                )

        print(
            f"⚠️ خطأ أثناء حفظ رسائل المستخدمين: {e}"
        )

    finally:

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

    # --------------------------------------------------
    # المستخدم
    # --------------------------------------------------

    user = update.effective_user

    if not user:
        return

    user_id = user.id

    # --------------------------------------------------
    # إضافة الرسالة للذاكرة
    # --------------------------------------------------

    _pending_messages[user_id] = (
        _pending_messages.get(
            user_id,
            0
        )
        + 1
    )

    _pending_user_data[user_id] = (
        user.username,
        user.first_name
    )

    # --------------------------------------------------
    # تحديث الكاش مباشرة
    # --------------------------------------------------

    cached = _user_cache.get(user_id)

    if cached:

        cached["messages"] = (
            cached.get("messages", 0)
            + 1
        )

        cached["username"] = user.username
        cached["first_name"] = user.first_name

    # --------------------------------------------------
    # حفظ كل 10 رسائل
    # --------------------------------------------------

    if _pending_messages[user_id] >= MESSAGE_BATCH_SIZE:

        await flush_user_messages()
