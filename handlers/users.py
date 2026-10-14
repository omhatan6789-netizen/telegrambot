from datetime import datetime
from html import escape
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank
from handlers.points import get_points

from handlers.cache import (
    get_cached_user,
    set_cached_user,
    update_cached_profile,
    increment_cached_messages,
    get_user_data,
    ensure_cached_user,
)

from handlers import cache as _cache_module

_user_cache = _cache_module._user_cache


# =========================================================
# قفل عملية الحفظ
# =========================================================

_flush_lock = None


def _get_flush_lock():
    global _flush_lock

    if _flush_lock is None:
        _flush_lock = asyncio.Lock()

    return _flush_lock


# =========================================================
# تحديد المستخدم لأمر ايدي
# =========================================================

async def get_id_target_user(update, context):

    if not update.message:
        return None

    message = update.message

    # =====================================================
    # الرد على رسالة
    # =====================================================

    if message.reply_to_message:

        replied_user = (
            message.reply_to_message.from_user
        )

        if replied_user:
            return replied_user

    # =====================================================
    # قراءة النص
    # =====================================================

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 2:
        return update.effective_user

    target = parts[-1].strip()

    # =====================================================
    # ID
    # =====================================================

    if target.lstrip("-").isdigit():

        try:

            return await context.bot.get_chat(
                int(target)
            )

        except Exception:

            return None

    # =====================================================
    # Username
    # =====================================================

    username = target.lstrip("@")

    if username:

        # محاولة الكاش أولاً
        try:

            cached_user = get_cached_user(
                username
            )

            if cached_user:
                return cached_user

        except Exception:

            pass

        # Telegram API
        try:

            return await context.bot.get_chat(
                f"@{username}"
            )

        except Exception:

            return None

    return None


# =========================================================
# إنشاء المستخدم إذا لم يكن موجوداً
# =========================================================

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


# =========================================================
# أمر ايدي
# =========================================================

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

    # =====================================================
    # الكاش
    # =====================================================

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

    else:

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

        else:

            joined_date = await asyncio.to_thread(
                _create_user_if_missing_sync,
                user_id,
                username_value,
                first_name_value,
            )

            messages = 0

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

    # =====================================================
    # الرتبة
    # =====================================================

    # =====================================================
    # الرتبة الحالية
    # =====================================================

    try:

        # حذف الرتبة القديمة من الكاش
        try:
            from handlers.cache import _rank_cache

            _rank_cache.pop(user_id, None)

        except Exception:
            pass

        # جلب الرتبة الحالية
        rank = await asyncio.to_thread(
            get_rank,
            user_id,
            update.effective_chat.id if update.effective_chat else None
        )

    except Exception:

        rank = "عضو"

    if not rank:
        rank = "عضو"

    # =====================================================
    # النقاط
    # =====================================================

    try:

        points = await asyncio.to_thread(
            get_points,
            user_id
        )

    except Exception:

        points = 0

    if points is None:
        points = 0

    # =====================================================
    # تحديث الكاش
    # =====================================================

    cached = get_cached_user(
        user_id
    )

    if cached is not None:

        cached["rank"] = rank
        cached["points"] = points

    else:

        set_cached_user(
            user_id,
            {
                "user_id": user_id,
                "messages": messages,
                "rank": rank,
                "joined_date": joined_date,
                "username": username_value,
                "first_name": first_name_value or "",
                "points": points,
            }
        )

    update_cached_profile(
        user_id,
        username=username_value,
        first_name=first_name_value,
    )

    # =====================================================
    # معلومات Telegram
    # =====================================================

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

        update_cached_profile(
            user_id,
            username=username_value,
            first_name=first_name_value,
        )

    except Exception:

        pass

    # =====================================================
    # تنسيق النص
    # =====================================================

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

    # =====================================================
    # صورة البروفايل
    # =====================================================

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


# =========================================================
# حفظ تاريخ دخول المستخدم
# =========================================================

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

    try:

        rank = await asyncio.to_thread(
            get_rank,
            user.id
        )

    except Exception:

        rank = "عضو"

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

    # =====================================================
    # حفظ العضو في كاش المجموعة مباشرة
    # =====================================================

    try:

        conn = connect()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO group_members
            (
                chat_id,
                user_id,
                username,
                first_name,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT (chat_id, user_id)
            DO UPDATE SET

                username = EXCLUDED.username,

                first_name = EXCLUDED.first_name,

                last_seen = EXCLUDED.last_seen
            """,
            (
                update.effective_chat.id,
                user.id,
                user.username,
                user.first_name,
                datetime.now().isoformat(),
            )
        )

        conn.commit()

        cur.close()
        conn.close()

    except Exception as e:

        print(
            f"⚠️ خطأ أثناء حفظ عضو المجموعة: {e}"
        )


# =========================================================
# كاش الرسائل
# =========================================================

_pending_messages = {}
_pending_user_data = {}

# =========================================================
# كاش أعضاء المجموعات
# =========================================================

_pending_group_members = {}

MESSAGE_BATCH_SIZE = 10
GROUP_MEMBER_FLUSH_SIZE = 20


# =========================================================
# حفظ البيانات في قاعدة البيانات
# =========================================================

def _flush_user_messages_sync(
    messages,
    user_data,
    group_members
):

    conn = connect()

    cur = None

    try:

        cur = conn.cursor()

        # =================================================
        # تحديث كاش أعضاء القروبات
        # =================================================

        for key, data in group_members.items():

            chat_id, user_id = key

            username, first_name, last_seen = data

            cur.execute(
                """
                INSERT INTO group_members
                (
                    chat_id,
                    user_id,
                    username,
                    first_name,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT (chat_id, user_id)
                DO UPDATE SET

                    username =
                        EXCLUDED.username,

                    first_name =
                        EXCLUDED.first_name,

                    last_seen =
                        EXCLUDED.last_seen
                """,
                (
                    chat_id,
                    user_id,
                    username,
                    first_name,
                    last_seen,
                )
            )

        # =================================================
        # تحديث رسائل المستخدمين
        # =================================================

        for user_id, count in messages.items():

            data = user_data.get(
                user_id
            )

            if not data:
                continue

            username, first_name = data

            cur.execute(
                """
                UPDATE users
                SET
                    messages =
                        COALESCE(messages, 0) + ?,
                    username = ?,
                    first_name = ?
                WHERE user_id = ?
                """,
                (
                    count,
                    username,
                    first_name,
                    user_id
                )
            )

            # =================================================
            # إذا المستخدم غير موجود
            # =================================================

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


# =========================================================
# تفريغ الكاش
# =========================================================

async def flush_user_messages():

    global _pending_messages
    global _pending_user_data
    global _pending_group_members

    lock = _get_flush_lock()

    async with lock:

        if (
            not _pending_messages
            and not _pending_group_members
        ):
            return

        # =================================================
        # أخذ نسخة من البيانات
        # =================================================

        messages = _pending_messages
        user_data = _pending_user_data
        group_members = _pending_group_members

        # =================================================
        # تفريغ الذاكرة
        # =================================================

        _pending_messages = {}
        _pending_user_data = {}
        _pending_group_members = {}

        try:

            await asyncio.to_thread(
                _flush_user_messages_sync,
                messages,
                user_data,
                group_members,
            )

        except Exception as e:

            # =================================================
            # استرجاع الرسائل إذا فشل الحفظ
            # =================================================

            for user_id, count in messages.items():

                _pending_messages[user_id] = (
                    _pending_messages.get(
                        user_id,
                        0
                    )
                    + count
                )

            # =================================================
            # استرجاع بيانات المستخدمين
            # =================================================

            for user_id, data in user_data.items():

                _pending_user_data[user_id] = data

            # =================================================
            # استرجاع أعضاء المجموعات
            # =================================================

            for key, data in group_members.items():

                _pending_group_members[key] = data

            print(
                f"⚠️ خطأ أثناء حفظ رسائل المستخدمين: {e}"
            )


# =========================================================
# جدولة تفريغ الكاش
# =========================================================

def _schedule_message_flush():

    try:

        asyncio.create_task(
            flush_user_messages()
        )

    except RuntimeError:

        pass


# =========================================================
# حفظ رسالة المستخدم
# =========================================================

async def save_user_message(
    update,
    context
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    # =====================================================
    # المجموعات فقط
    # =====================================================

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    user = update.effective_user

    if not user:
        return

    # تجاهل البوتات
    if user.is_bot:
        return

    user_id = user.id
    chat_id = chat.id

    # =====================================================
    # إضافة العضو إلى كاش المجموعة
    # =====================================================

    _pending_group_members[
        (chat_id, user_id)
    ] = (
        user.username,
        user.first_name,
        datetime.now().isoformat()
    )

    # =====================================================
    # عداد الرسائل
    # =====================================================

    _pending_messages[user_id] = (
        _pending_messages.get(
            user_id,
            0
        )
        + 1
    )

    # =====================================================
    # بيانات المستخدم
    # =====================================================

    _pending_user_data[user_id] = (
        user.username,
        user.first_name
    )

    # =====================================================
    # تحديث الكاش السريع
    # =====================================================

    increment_cached_messages(
        user_id,
        amount=1,
        username=user.username,
        first_name=user.first_name,
    )

    # =====================================================
    # تفريغ عند الوصول للحد
    # =====================================================

    if (
        _pending_messages[user_id]
        >= MESSAGE_BATCH_SIZE
    ):

        _schedule_message_flush()

    elif (
        len(_pending_group_members)
        >= GROUP_MEMBER_FLUSH_SIZE
    ):

        _schedule_message_flush()
