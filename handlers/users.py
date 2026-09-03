from datetime import datetime
from html import escape
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank


_user_cache = {}

# ==================================================
# قفل عملية حفظ الرسائل
# ==================================================

_flush_lock = None


def _get_flush_lock():
    global _flush_lock

    if _flush_lock is None:
        _flush_lock = asyncio.Lock()

    return _flush_lock


# ==================================================
# تحديد الشخص المستهدف في أمر ايدي
# ==================================================

async def get_id_target_user(update, context):

    if not update.message:
        return None

    message = update.message

    # الرد على شخص
    if message.reply_to_message:

        replied_user = (
            message.reply_to_message.from_user
        )

        if replied_user:
            return replied_user

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    # ايدي فقط = صاحب الرسالة
    if len(parts) < 2:
        return update.effective_user

    target = parts[-1].strip()

    # آيدي
    if target.isdigit():

        try:

            return await context.bot.get_chat(
                int(target)
            )

        except Exception:

            return None

    # يوزر
    if target.startswith("@"):

        try:

            return await context.bot.get_chat(
                target
            )

        except Exception:

            return None

    return None


# ==================================================
# أمر ايدي
# ==================================================

async def user_id_command(update, context):

    if not update.message:
        return

    if not update.effective_user:
        return

    target = await get_id_target_user(
        update,
        context
    )

    if not target:

        await update.message.reply_text(
            "❌ حدد الشخص بالرد أو اليوزر أو الآيدي."
        )

        return

    user_id = target.id

    cached = _user_cache.get(user_id)

    if cached:

        messages = cached.get(
            "messages",
            0
        )

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
                (user_id,)
            )

            data = cur.fetchone()

            if data:

                messages = data[0] or 0
                joined_date = (
                    data[2]
                    or "غير معروف"
                )

            else:

                joined_date = (
                    datetime.now().strftime(
                        "%Y/%m/%d"
                    )
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
                        user_id,
                        getattr(
                            target,
                            "username",
                            None
                        ),
                        getattr(
                            target,
                            "first_name",
                            ""
                        ),
                        0,
                        "عضو",
                        joined_date
                    )
                )

                conn.commit()

                messages = 0

            try:
                cur.close()
            except Exception:
                pass

        finally:

            conn.close()

    # ==================================================
    # الرتبة من المصدر الصحيح
    # ==================================================

    rank = get_rank(user_id)

    # تحديث الكاش
    _user_cache[user_id] = {

        "messages": messages,

        "rank": rank,

        "joined_date": joined_date,

        "username": getattr(
            target,
            "username",
            None
        ),

        "first_name": getattr(
            target,
            "first_name",
            ""
        ),
    }

    username_value = getattr(
        target,
        "username",
        None
    )

    first_name_value = getattr(
        target,
        "first_name",
        None
    )

    username = (
        f"@{username_value}"
        if username_value
        else "لا يوجد"
    )

    bio = "لا يوجد"

    # ==================================================
    # معلومات Telegram
    # ==================================================

    try:

        user_info = await context.bot.get_chat(
            user_id
        )

        if user_info.bio:

            bio = user_info.bio

        if not first_name_value:

            first_name_value = (
                user_info.first_name
                or "غير معروف"
            )

        if (
            not username_value
            and user_info.username
        ):

            username = (
                f"@{user_info.username}"
            )

    except Exception:

        pass

    # ==================================================
    # حماية HTML
    # ==================================================

    safe_name = escape(
        first_name_value
        or "غير معروف"
    )

    safe_username = escape(
        username
    )

    safe_bio = escape(
        bio
    )

    safe_joined_date = escape(
        str(joined_date)
    )

    safe_rank = escape(
        rank
    )

    # ==================================================
    # رتبة صاحب البوت Spoiler
    # ==================================================

    if user_id == 8453977662:

        rank_text = (
            f"<tg-spoiler>{safe_rank}</tg-spoiler>"
        )

    else:

        rank_text = safe_rank

    text = f"""
🌷ᵂᴱᴸᶜᴼᴹᴱ ᵀᴼ ᴳᴿᴼᵁᴾ🌷
- عـيـونـي تـنـظـفـت يـوم شـفـت افـتارك
🖱️ Name 𖦹 {safe_name}
🖥️ USER 𖦹 {safe_username}
💬 MSG 𖦹 {messages}
🛡 STA 𖦹 {rank_text}
ℹ️ ID 𖦹 {user_id}
🗒 BIO 𖦹 {safe_bio}
📅 Joined Group 𖦹 {safe_joined_date}
"""

    # ==================================================
    # صورة البروفايل
    # ==================================================

    try:

        photos = await context.bot.get_user_profile_photos(
            user_id,
            limit=1
        )

        if photos.total_count > 0:

            photo = (
                photos.photos[0][-1].file_id
            )

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

    joined_date = (
        datetime.now().strftime(
            "%Y/%m/%d"
        )
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

        # نستخدم الرتبة الموجودة فعليًا
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
# تجميع الرسائل
# ==================================================

_pending_messages = {}
_pending_user_data = {}

MESSAGE_BATCH_SIZE = 10


# ==================================================
# تنفيذ الحفظ في Thread
# ==================================================

def _flush_user_messages_sync(
    messages,
    user_data
):

    conn = connect()

    try:

        cur = conn.cursor()

        for user_id, count in messages.items():

            data = user_data.get(user_id)

            if not data:
                continue

            username, first_name = data

            # محاولة تحديث المستخدم الموجود
            cur.execute(
                """
                UPDATE users
                SET
                    messages =
                        COALESCE(messages, 0) + ?,
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

            # المستخدم غير موجود
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
                            COALESCE(
                                users.messages,
                                0
                            )
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

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# ==================================================
# حفظ الرسائل المعلقة
# ==================================================

async def flush_user_messages():

    global _pending_messages
    global _pending_user_data

    lock = _get_flush_lock()

    async with lock:

        if not _pending_messages:
            return

        # نسخ البيانات بسرعة داخل event loop
        messages = _pending_messages
        user_data = _pending_user_data

        _pending_messages = {}
        _pending_user_data = {}

        try:

            # ==================================================
            # PostgreSQL خارج event loop
            # ==================================================

            await asyncio.to_thread(
                _flush_user_messages_sync,
                messages,
                user_data
            )

            # ==================================================
            # تحديث الكاش
            # ==================================================

            for user_id, count in messages.items():

                data = user_data.get(
                    user_id
                )

                if not data:
                    continue

                username, first_name = data

                cached = _user_cache.get(
                    user_id
                )

                if cached:

                    cached["messages"] = (
                        cached.get(
                            "messages",
                            0
                        )
                        + count
                    )

                    cached["username"] = (
                        username
                    )

                    cached["first_name"] = (
                        first_name
                    )

                else:

                    _user_cache[user_id] = {

                        "messages": count,

                        "rank": "عضو",

                        "joined_date": (
                            datetime.now().strftime(
                                "%Y/%m/%d"
                            )
                        ),

                        "username": username,

                        "first_name": first_name,
                    }

        except Exception as e:

            # ==================================================
            # إعادة الرسائل في حال فشل الحفظ
            # ==================================================

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


# ==================================================
# حفظ رسالة المستخدم
# ==================================================

async def save_user_message(
    update,
    context
):

    if not update.message:
        return

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

    user_id = user.id

    # ==================================================
    # زيادة العداد في الذاكرة فقط
    # ==================================================

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

    # ==================================================
    # تحديث الكاش مباشرة
    # ==================================================

    cached = _user_cache.get(
        user_id
    )

    if cached:

        cached["messages"] = (
            cached.get(
                "messages",
                0
            )
            + 1
        )

        cached["username"] = (
            user.username
        )

        cached["first_name"] = (
            user.first_name
        )

    # ==================================================
    # الحفظ فقط عند الوصول للدفعة
    # ==================================================

    if (
        _pending_messages[user_id]
        >= MESSAGE_BATCH_SIZE
    ):

        await flush_user_messages()
