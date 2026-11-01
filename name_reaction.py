import re
import json
from pathlib import Path
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
ENABLE_REPLY = "طيب لا تنفخ فعلت لك الردود"
DISABLE_REPLY = "طيب عطلته"
HANDLER_GROUP = 1100
CONTROL_HANDLER_GROUP = 1099
# ملف حفظ حالة الردود
SETTINGS_FILE = Path("name_reaction_settings.json")
# الحالة الافتراضية
DEFAULT_ENABLED = True
_client = None
_handler = None
_control_handler = None
# ==========================================
# حالة الردود والحفظ
# ==========================================
def load_reply_state():
    try:
        if SETTINGS_FILE.exists():
            with SETTINGS_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return bool(data.get("enabled", DEFAULT_ENABLED))
    except Exception as exc:
        print(f"[NAME REACTION] Settings load error: {exc}")
    return DEFAULT_ENABLED
def save_reply_state():
    try:
        temp_file = SETTINGS_FILE.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(
                {"enabled": replies_enabled},
                file,
                ensure_ascii=False
            )
        temp_file.replace(SETTINGS_FILE)
    except Exception as exc:
        print(f"[NAME REACTION] Settings save error: {exc}")
replies_enabled = load_reply_state()
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
        return ONLINE_REPLY
    except Exception as exc:
        print(f"[NAME REACTION] Status error: {exc}")
        return ONLINE_REPLY
# ==========================================
# تفعيل وتعطيل الردود
# ==========================================
async def _reply_control_handler(client, message):
    global replies_enabled
    if not message.outgoing:
        return
    text = (message.text or message.caption or "").strip()
    if text == "تفعيل الردود":
        replies_enabled = True
        save_reply_state()
        try:
            await message.reply_text(ENABLE_REPLY)
            print("[NAME REACTION] Replies enabled.")
        except FloodWait as exc:
            print(f"[NAME REACTION] Control FloodWait: {exc.value}s")
        except Exception as exc:
            print(f"[NAME REACTION] Enable reply error: {exc}")
    elif text == "تعطيل الردود":
        replies_enabled = False
        save_reply_state()
        try:
            await message.reply_text(DISABLE_REPLY)
            print("[NAME REACTION] Replies disabled.")
        except FloodWait as exc:
            print(f"[NAME REACTION] Control FloodWait: {exc.value}s")
        except Exception as exc:
            print(f"[NAME REACTION] Disable reply error: {exc}")
# ==========================================
# استقبال الرسائل واكتشاف نواف
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
    # إيقاف الردود إذا كانت معطلة
    if not replies_enabled:
        return
    # تحديد الرد حسب حالة الحساب
    reply = await get_account_status()
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
    global _client, _handler, _control_handler
    if _handler is not None:
        return
    _client = get_music_client()
    if _client is None:
        print("[NAME REACTION] Music account is not connected.")
        return
    # معالج التفعيل والتعطيل
    _control_handler = MessageHandler(
        _reply_control_handler,
        filters.outgoing
        & (filters.text | filters.caption)
    )
    # معالج اكتشاف كلمة نواف
    _handler = MessageHandler(
        _name_reaction_handler,
        filters.group
        & (filters.text | filters.caption)
        & filters.incoming
    )
    _client.add_handler(
        _control_handler,
        group=CONTROL_HANDLER_GROUP
    )
    _client.add_handler(
        _handler,
        group=HANDLER_GROUP
    )
    print("[NAME REACTION] Started successfully.")
    print(f"[NAME REACTION] Replies enabled: {replies_enabled}")
# ==========================================
# الإيقاف
# ==========================================
async def shutdown_name_reaction():
    global _client, _handler, _control_handler
    if _client is not None:
        if _handler is not None:
            try:
                _client.remove_handler(
                    _handler,
                    group=HANDLER_GROUP
                )
            except Exception as exc:
                print(f"[NAME REACTION] Stop error: {exc}")
        if _control_handler is not None:
            try:
                _client.remove_handler(
                    _control_handler,
                    group=CONTROL_HANDLER_GROUP
                )
            except Exception as exc:
                print(f"[NAME REACTION] Control stop error: {exc}")
    _handler = None
    _control_handler = None
    _client = None
    print("[NAME REACTION] Stopped.")
