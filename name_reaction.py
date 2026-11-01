
import re

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.errors import FloodWait

from music_call import get_music_client


# ==========================================
# الإعدادات
# ==========================================

TARGET_WORD = "نواف"
REACTION_EMOJI = "😴"

HANDLER_GROUP = 1100

_client = None
_handler = None


# ==========================================
# اكتشاف الكلمة
# ==========================================

WORD_PATTERN = re.compile(
    rf"(?<!\w){re.escape(TARGET_WORD)}(?!\w)"
)


# ==========================================
# استقبال الرسائل والتفاعل
# ==========================================

async def _name_reaction_handler(client, message):

    if not message.from_user:
        return

    # تجاهل رسائل الحساب نفسه
    if message.from_user.is_self:
        return

    # قراءة النص أو وصف الوسائط
    text = message.text or message.caption or ""

    if not text:
        return

    # التأكد من وجود كلمة نواف
    if not WORD_PATTERN.search(text):
        return

    try:
        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=REACTION_EMOJI
        )

        print(
            f"[NAME REACTION] Reacted to message "
            f"{message.id} in chat {message.chat.id}"
        )

    except FloodWait as exc:
        print(f"[NAME REACTION] FloodWait: {exc.value}s")

    except Exception as exc:
        print(f"[NAME REACTION] Error: {exc}")


# ==========================================
# تشغيل السكربت
# ==========================================

async def start_name_reaction():

    global _client, _handler

    if _handler is not None:
        return

    _client = get_music_client()

    if _client is None:
        print("[NAME REACTION] Music account is not connected.")
        return

    _handler = MessageHandler(
        _name_reaction_handler,
        filters.group
        & (filters.text | filters.caption)
        & filters.incoming
    )

    _client.add_handler(
        _handler,
        group=HANDLER_GROUP
    )

    print("[NAME REACTION] Started successfully.")


# ==========================================
# إيقاف السكربت
# ==========================================

async def shutdown_name_reaction():

    global _client, _handler

    if _client is not None and _handler is not None:

        try:
            _client.remove_handler(
                _handler,
                group=HANDLER_GROUP
            )

        except Exception as exc:
            print(f"[NAME REACTION] Stop error: {exc}")

    _handler = None
    _client = None

    print("[NAME REACTION] Stopped.")
