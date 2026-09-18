from datetime import datetime
from html import escape
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank

from handlers.cache import (
    get_cached_user,
    set_cached_user,
    update_cached_profile,
    increment_cached_messages,
    get_user_data,
    ensure_cached_user,
)


# ==================================================
# توافق مع أي كود قديم يستخدم _user_cache
# ==================================================

from handlers import cache as _cache_module

_user_cache = _cache_module._user_cache


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
# إنشاء مستخدم في قاعدة البيانات عند الحاجة
# ==================================================

def _create_user_if_missing_sync(
    user_id,
    username,
    first_name,
):
    conn = connect()

    cur = None

    try:

        cur = conn.cursor()

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
                user_id,
                username,
                first_name,
                0,
                "عضو",
                joined_date,
            )
        )

        conn.commit()

        return joined_date

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


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

    username_value = getattr(
        target,
        "username",
        None
    )

    first_name_value = getattr(
        target,
        "first_name",
        ""
    )

    # ==================================================
    # نحاول أخذ البيانات من الكاش المركزي
    # ==================================================

    cached = get_cached_user(
        user_id
    )

    if cached is not None:

        messages = cached.get(
            "messages",
            0
        )

        joined_date = cached.get(
            "joined_date",
            "غير معروف"
        )

        rank = cached.get(
            "rank",
            "عضو"
        )

    else:

        # ==================================================
        # تحميل المستخدم من DB خارج event loop
        # ==================================================

        data = await get_user_data(
            user_id
        )

        if data is not None:

            messages = data.get(
                "messages",
                0
            )

            joined_date = data.get(
                "joined_date",
                "غير معروف"
            )

            rank = data.get(
                "rank",
                "عضو"
            )

        else:

            # ==================================================
            # المستخدم غير موجود
            # ننشئه خارج event loop
            # ==================================================

            joined_date = await asyncio.to_thread(
                _create_user_if_missing_sync,
                user_id,
                username_value,
                first_name_value,
            )

            messages = 0
            rank = "عضو"

            # نخليه موجودًا في الكاش
            set_cached_user(
                user_id,
                {
                    "user_id": user_id,
                    "messages": 0,
                    "rank": "عضو",
                    "joined_date": joined_date,
                    "username": username_value,
                    "first_name": first_name_value or "",
                    "points": 0,
                }
            )

        # ==================================================
        # إذا كانت الرتبة قد تكون مختلفة في جدول الرتب
        # نقرأها خارج event loop
        # ==================================================

        try:

            rank = await asyncio.to_thread(
                get_rank,
                user_id
            )

        except Exception:

            rank = rank or "عضو"

        cached = get_cached_user(
            user_id
        )

        if cached is not None:

            cached["rank"] = rank

    # ==================================================
    # تحديث بيانات Telegram في الكاش
    # ==================================================

    update_cached_profile(
        user_id,
        username=username_value,
        first_name=first_name_value,
    )

    # ==================================================
    # معلومات Telegram
    # ==================================================

    username = (
        f"@{username_value}"
        if username_value
        else "لا يوجد"
    )

    bio = "لا يوجد"

    try:

        user_info = await context.bot.get_chat(
            user_id
        )

        if getattr(
            user_info,
            "bio",
            None
        ):

            bio = user_info.bio

        if not first_name_value:

            first_name_value = (
                getattr(
                    user_info,
                    "first_name",
                    None
                )
                or "غير معروف"
            )

        if (
            not username_value
            and getattr(
                user_info,
                "username",
                None
            )
        ):

            username_value = user_info.username

            username = (
                f"@{username_value}"
            )

        # تحديث الكاش بالبيانات الأحدث
        update_cached_profile(
            user_id,
            username=username_value,
            first_name=first_name_value,
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
        rank or "عضو"
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

def _save_join_date_sync(
    user_id,
    username,
    first_name,
    joined_date,
):

    conn = connect()

    cur = None

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
                user_id,
                username,
                first_name,
                0,
                "عضو",
                joined_date,
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

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


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

    # ==================================================
    # DB خارج event loop
    # ==================================================

    try:

        await asyncio.to_thread(
            _save_join_date_sync,
            user.id,
            user.username,
            user.first_name,
            joined_date,
        )

    except Exception as e:

        print(
            f"⚠️ خطأ أثناء حفظ تاريخ دخول المستخدم: {e}"
        )

        return

    # ==================================================
    # الرتبة خارج event loop
    # ==================================================

    try:

        rank = await asyncio.to_thread(
            get_rank,
            user.id
        )

    except Exception:

        rank = "عضو"

    # ==================================================
    # الكاش المركزي
    # ==================================================

    set_cached_user(
        user.id,
        {
            "user_id": user.id,
            "messages": 0,
            "rank": rank,
            "joined_date": joined_date,
            "username": user.username,
            "first_name": user.first_name or "",
            "points": 0,
        }
    )


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

    cur = None

    try:

        cur = conn.cursor()

        for user_id, count in messages.items():

            data = user_data.get(
                user_id
            )

            if not data:
                continue

            username, first_name = data

            # ==================================================
            # محاولة تحديث المستخدم الموجود
            # ==================================================

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

            # ==================================================
            # المستخدم غير موجود
            # ==================================================

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

        if cur is not None:

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

        # ==================================================
        # نسخ البيانات بسرعة
        # ==================================================

        messages = _pending_messages
        user_data = _pending_user_data

        _pending_messages = {}
        _pending_user_data = {}

        try:

            # ==================================================
            # DB خارج event loop
            # ==================================================

            await asyncio.to_thread(
                _flush_user_messages_sync,
                messages,
                user_data
            )

            # ==================================================
            # مهم:
            #
            # لا نزيد messages هنا!
            #
            # save_user_message() زاد الكاش مسبقًا.
            # لو زدناه هنا راح يتضاعف العداد.
            # ==================================================

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
# تشغيل Flush في الخلفية
# ==================================================

def _schedule_message_flush():

    try:

        asyncio.create_task(
            flush_user_messages()
        )

    except RuntimeError:

        # لا يوجد event loop متاح
        pass


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
    # زيادة الرسائل المعلقة
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
    # تحديث الكاش المركزي مباشرة
    #
    # هذا يجعل #الرسائل وملف المستخدم
    # محدثين بدون انتظار DB.
    # ==================================================

    increment_cached_messages(
        user_id,
        amount=1,
        username=user.username,
        first_name=user.first_name,
    )

    # ==================================================
    # إذا وصلت الدفعة إلى 10:
    #
    # لا ننتظر DB!
    # نشغل الحفظ بالخلفية.
    # ==================================================

    if (
        _pending_messages[user_id]
        >= MESSAGE_BATCH_SIZE
    ):

        _schedule_message_flush()
