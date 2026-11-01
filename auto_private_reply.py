
import asyncio
import time

from pyrogram import filters
from pyrogram.handlers import MessageHandler

from database import connect
from music_call import get_music_client


# ==========================================
# الإعدادات
# ==========================================

REPLY_TEXT = (
    "الملك نواف مشغول شوي لو فضى لك بيرد عليك🙏🏻"
)

REPLY_INTERVAL = 24 * 60 * 60  # 24 ساعة

_client = None
_handler = None

_HANDLER_GROUP = 1000

_user_locks = {}


# ==========================================
# إنشاء جدول Supabase
# ==========================================

def _init_database():
    conn = None
    cur = None

    try:
        conn = connect()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS auto_private_replied (
                user_id BIGINT PRIMARY KEY,
                replied_at BIGINT NOT NULL
            )
        """)

        conn.commit()

        print("[AUTO REPLY] Supabase table ready.")

    except Exception:
        if conn:
            conn.rollback()

        raise

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# ==========================================
# تسجيل الرد في Supabase
# ==========================================

def _claim_reply_slot(user_id, now):
    """
    حجز الرد إذا انتهت مدة 24 ساعة.
    يعيد (نجاح الحجز، وقت الرد السابق).
    """

    conn = None
    cur = None

    try:
        conn = connect()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT replied_at
            FROM auto_private_replied
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        previous_time = int(row[0]) if row else None

        if previous_time is not None:
            if now - previous_time < REPLY_INTERVAL:
                return False, previous_time

        cur.execute(
            """
            INSERT INTO auto_private_replied (
                user_id,
                replied_at
            )
            VALUES (?, ?)

            ON CONFLICT (user_id)
            DO UPDATE SET replied_at = EXCLUDED.replied_at
            """,
            (user_id, now)
        )

        conn.commit()

        return True, previous_time

    except Exception:
        if conn:
            conn.rollback()

        raise

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# ==========================================
# استرجاع وقت الرد السابق عند فشل الإرسال
# ==========================================

def _restore_reply_time(user_id, previous_time):
    conn = None
    cur = None

    try:
        conn = connect()
        cur = conn.cursor()

        if previous_time is None:
            cur.execute(
                """
                DELETE FROM auto_private_replied
                WHERE user_id = ?
                """,
                (user_id,)
            )

        else:
            cur.execute(
                """
                UPDATE auto_private_replied
                SET replied_at = ?
                WHERE user_id = ?
                """,
                (previous_time, user_id)
            )

        conn.commit()

    except Exception:
        if conn:
            conn.rollback()

        raise

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# ==========================================
# استقبال الرسائل الخاصة
# ==========================================

async def _private_message_handler(client, message):

    if not message.from_user:
        return

    user = message.from_user

    # تجاهل الحسابات الآلية
    if user.is_bot:
        return

    user_id = user.id

    # قفل مستقل لكل مستخدم
    lock = _user_locks.setdefault(
        user_id,
        asyncio.Lock()
    )

    async with lock:

        # حجز الرد في قاعدة البيانات
        try:
            should_reply, previous_time = await asyncio.to_thread(
                _claim_reply_slot,
                user_id,
                int(time.time())
            )

        except Exception as exc:
            print(
                f"[AUTO REPLY] Database error: {exc}"
            )
            return

        # سبق الرد عليه خلال آخر 24 ساعة
        if not should_reply:
            return

        # إرسال الرد
        try:
            await message.reply_text(REPLY_TEXT)

            print(
                f"[AUTO REPLY] Replied to user {user_id}"
            )

        except Exception as exc:

            print(
                f"[AUTO REPLY] Send error for {user_id}: {exc}"
            )

            # استرجاع وقت الرد السابق حتى لا نخسر المحاولة
            try:
                await asyncio.to_thread(
                    _restore_reply_time,
                    user_id,
                    previous_time
                )

            except Exception as db_exc:
                print(
                    f"[AUTO REPLY] Restore error: {db_exc}"
                )


# ==========================================
# تشغيل الميزة
# ==========================================

async def start_auto_private_reply():
    global _client, _handler

    if _handler is not None:
        return

    _client = get_music_client()

    if _client is None:
        print(
            "[AUTO REPLY] Music account is not connected."
        )
        return

    try:
        await asyncio.to_thread(_init_database)

        _handler = MessageHandler(
            _private_message_handler,
            filters.private & filters.incoming
        )

        _client.add_handler(
            _handler,
            group=_HANDLER_GROUP
        )

        print(
            "[AUTO REPLY] Private auto-reply started successfully."
        )

    except Exception as exc:
        _handler = None
        _client = None

        print(
            f"[AUTO REPLY] Failed to start: {exc}"
        )


# ==========================================
# إيقاف الميزة
# ==========================================

async def shutdown_auto_private_reply():
    global _client, _handler

    if _client is not None and _handler is not None:

        try:
            _client.remove_handler(
                _handler,
                group=_HANDLER_GROUP
            )

        except Exception as exc:
            print(
                f"[AUTO REPLY] Handler removal error: {exc}"
            )

    _handler = None
    _client = None
    _user_locks.clear()

    print(
        "[AUTO REPLY] Private auto-reply stopped."
    )
