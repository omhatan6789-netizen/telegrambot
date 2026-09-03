from datetime import datetime
from html import escape

from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank


# ==================================================
# كاش المستخدمين
# ==================================================

_user_cache = {}


# ==================================================
# أمر ايدي
# ==================================================

async def user_id_command(update, context):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user

    cached = _user_cache.get(user.id)

    if cached:
        messages = cached.get("messages", 0)
        joined_date = cached.get("joined_date", "غير معروف")
    else:
        conn = connect()

        try:
            cur = conn.cursor()

            cur.execute("""
                SELECT messages, rank, joined_date
                FROM users
                WHERE user_id=?
            """, (user.id,))

            data = cur.fetchone()

            if data:
                messages = data[0] or 0
                joined_date = data[2] or "غير معروف"

            else:
                joined_date = datetime.now().strftime("%Y/%m/%d")

                cur.execute("""
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
                """, (
                    user.id,
                    user.username,
                    user.first_name,
                    0,
                    "عضو",
                    joined_date
                ))

                conn.commit()

                messages = 0

            try:
                cur.close()
            except Exception:
                pass

        finally:
            conn.close()

    # ==================================================
    # الرتبة تؤخذ دائمًا من المصدر الصحيح
    # وليس من الكاش القديم
    # ==================================================

    rank = get_rank(user.id)

    # تحديث الكاش
    _user_cache[user.id] = {
        "messages": messages,
        "rank": rank,
        "joined_date": joined_date,
        "username": user.username,
        "first_name": user.first_name,
    }

    username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )

    bio = "لا يوجد"

    try:
        user_info = await context.bot.get_chat(user.id)

        if user_info.bio:
            bio = user_info.bio

    except Exception:
        pass

    # ==================================================
    # حماية النصوص من HTML
    # ==================================================

    safe_name = escape(
        user.first_name or "غير معروف"
    )

    safe_username = escape(
        username
    )

    safe_rank = escape(
        rank
    )

    safe_bio = escape(
        bio
    )

    safe_joined_date = escape(
        str(joined_date)
    )

    # ==================================================
    # الرتبة Spoiler
    # ==================================================

    text = f"""
🌷ᵂᴱᴸᴯᴼᴹᴱ ᵀᴼ ᴳᴿᴼᵁᴾ🌷
- عـيـونـي تـنـظـفـت يـوم شـفـت افـتـارك
🖱️ Name 𖦹 {safe_name}
🖥️ USER 𖦹 {safe_username}
💬 MSG 𖦹 {messages}
🛡 STA 𖦹 <tg-spoiler>{safe_rank}</tg-spoiler>
ℹ️ ID 𖦹 {user.id}
🗒 BIO 𖦹 {safe_bio}
📅 Joined Group 𖦹 {safe_joined_date}
"""

    # ==================================================
    # صورة البروفايل
    # ==================================================

    try:
        photos = await context.bot.get_user_profile_photos(
            user.id,
            limit=1
        )

        if photos.total_count > 0:
            photo = photos.photos[0][-1].file_id

            await update.message.reply_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML"
            )

            return

    except Exception:
        pass

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ==================================================
# حفظ تاريخ دخول المستخدم
# ==================================================

async def save_join_date(update, context):
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

        cur.execute("""
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
        """, (
            user.id,
            user.username,
            user.first_name,
            0,
            "عضو",
            joined_date
        ))

        conn.commit()

        # نأخذ الرتبة الحقيقية بعد الإدخال
        rank = get_rank(user.id)

        _user_cache[user.id] = {
            "messages": 0,
            "rank": rank,
            "joined_date": joined_date,
            "username": user.username,
            "first_name": user.first_name,
        }

        try:
            cur.close()
        except Exception:
            pass

    finally:
        conn.close()


# ==================================================
# تجميع الرسائل قبل الحفظ
# ==================================================

_pending_messages = {}
_pending_user_data = {}

MESSAGE_BATCH_SIZE = 10


# ==================================================
# حفظ الرسائل المعلقة
# ==================================================

async def flush_user_messages():
    global _pending_messages
    global _pending_user_data

    if not _pending_messages:
        return

    messages = _pending_messages
    user_data = _pending_user_data

    _pending_messages = {}
    _pending_user_data = {}

    conn = connect()

    try:
        cur = conn.cursor()

        for user_id, count in messages.items():

            data = user_data.get(user_id)

            if not data:
                continue

            username, first_name = data

            cur.execute("""
                UPDATE users
                SET
                    messages = COALESCE(messages, 0) + ?,
                    username = ?,
                    first_name = ?
                WHERE user_id=?
            """, (
                count,
                username,
                first_name,
                user_id
            ))

            if cur.rowcount == 0:

                cur.execute("""
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
                """, (
                    user_id,
                    username,
                    first_name,
                    count,
                    "عضو",
                    datetime.now().strftime("%Y/%m/%d")
                ))

        conn.commit()

        # ==================================================
        # تحديث الكاش
        # ==================================================

        for user_id, count in messages.items():

            data = user_data.get(user_id)

            if not data:
                continue

            username, first_name = data

            cached = _user_cache.get(user_id)

            if cached:

                cached["messages"] = (
                    cached.get("messages", 0)
                    + count
                )

                cached["username"] = username
                cached["first_name"] = first_name

                # مهم:
                # لا نغير rank الموجود في الكاش

            else:

                rank = get_rank(user_id)

                _user_cache[user_id] = {
                    "messages": count,
                    "rank": rank,
                    "joined_date": datetime.now().strftime(
                        "%Y/%m/%d"
                    ),
                    "username": username,
                    "first_name": first_name,
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

        # إعادة البيانات للطابور
        for user_id, count in messages.items():

            _pending_messages[user_id] = (
                _pending_messages.get(user_id, 0)
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
# حفظ رسالة المستخدم
# ==================================================

async def save_user_message(update, context):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    # فقط القروبات
    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    user = update.effective_user

    if not user:
        return

    user_id = user.id

    _pending_messages[user_id] = (
        _pending_messages.get(user_id, 0)
        + 1
    )

    _pending_user_data[user_id] = (
        user.username,
        user.first_name
    )

    cached = _user_cache.get(user_id)

    if cached:

        cached["messages"] = (
            cached.get("messages", 0)
            + 1
        )

        cached["username"] = user.username
        cached["first_name"] = user.first_name

    # حفظ كل 10 رسائل
    if _pending_messages[user_id] >= MESSAGE_BATCH_SIZE:
        await flush_user_messages()
