
import re

from pyrogram import filters
from pyrogram.enums import UserStatus
from pyrogram.handlers import MessageHandler
from pyrogram.errors import FloodWait

from music_call import get_music_client


# ==========================================
# الإعدادات
# ==========================================

TARGET_WORD = "نواف"
REACTION_EMOJI = "😴"

ONLINE_REPLY = "مشغول👾"
OFFLINE_REPLY = "نايم"

HANDLER_GROUP = 1100

_client = None
_handler = None


# ==========================================
# اكتشاف كلمة نواف
# ==========================================

WORD_PATTERN = re.compile(
    rf"(?<!\w){re.escape(TARGET_WORD)}(?!\w)"
)


# ==========================================
# معرفة حالة الحساب
# ==========================================

async def get_account_status():

    try:
        me = await _client.get_me()

        if me.status == UserStatus.ONLINE:
            return ONLINE_REPLY

        if me.status == UserStatus.OFFLINE:
            return OFFLINE_REPLY

        # إذا كانت الحالة غير معروفة
        return ONLINE_REPLY

    except Exception as exc:
        print(f"[NAME REACTION] Status error: {exc}")
        return ONLINE_REPLY


# ==========================================
# استقبال الرسائل
# ==========================================

async def _name_reaction_handler(client, message):

    if not message.from_user:
        return

    if message.from_user.is_self:
        return

    text = message.text or message.caption or ""

    if not text:
        return

    if not WORD_PATTERN.search(text):
        return

    # تحديد الرد حسب حالة الحساب
    reply = await get_account_status()

    # إضافة التفاعل 😴
    try:
        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=REACTION_EMOJI
        )

        print(
            f"[NAME REACTION] Reacted in chat {message.chat.id}"
        )

    except FloodWait as exc:
        print(f"[NAME REACTION] Reaction FloodWait: {exc.value}s")

    except Exception as exc:
        print(f"[NAME REACTION] Reaction error: {exc}")

    # الرد على الرسالة
    try:
        await message.reply_text(reply)

        print(
            f"[NAME REACTION] Replied: {reply}"
        )

    except FloodWait as exc:
        print(f"[NAME REACTION] Reply FloodWait: {exc.value}s")

    except Exception as exc:
        print(f"[NAME REACTION] Reply error: {exc}")


# ==========================================
# التشغيل
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
# الإيقاف
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
