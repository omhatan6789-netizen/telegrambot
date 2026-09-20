# handlers/send.py

import asyncio
import re
from html import escape

from telegram import (
    Update,
    MessageEntity,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import connect
from handlers.cache import get_user_data


# =========================================================
# الإعدادات
# =========================================================

SEND_COMMAND_PATTERN = r"^/send(?:@[A-Za-z0-9_]+)?\s+[\s\S]+$"

# نخزن القروبات والقنوات التي عرفنا أن البوت موجود فيها.
SEND_CHATS_TABLE = "send_bot_chats"


# =========================================================
# إنشاء جدول القروبات والقنوات
# =========================================================

def create_send_tables():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SEND_CHATS_TABLE} (
                chat_id BIGINT PRIMARY KEY,
                chat_type TEXT NOT NULL,
                title TEXT,
                username TEXT,
                active BOOLEAN DEFAULT TRUE
            )
            """
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


# =========================================================
# تسجيل القروب / القناة
# =========================================================

def _save_chat_sync(chat):
    if not chat:
        return

    if chat.type not in ("group", "supergroup", "channel"):
        return

    title = chat.title or ""
    username = chat.username or ""

    conn = connect()
    cur = conn.cursor()

    try:
        # نحاول التحديث أولًا
        cur.execute(
            f"""
            UPDATE {SEND_CHATS_TABLE}
            SET
                chat_type = %s,
                title = %s,
                username = %s,
                active = TRUE
            WHERE chat_id = %s
            """,
            (
                chat.type,
                title,
                username,
                chat.id,
            ),
        )

        if cur.rowcount == 0:
            cur.execute(
                f"""
                INSERT INTO {SEND_CHATS_TABLE}
                    (chat_id, chat_type, title, username, active)
                VALUES
                    (%s, %s, %s, %s, TRUE)
                """,
                (
                    chat.id,
                    chat.type,
                    title,
                    username,
                ),
            )

        conn.commit()

    finally:
        cur.close()
        conn.close()


async def track_send_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يسجل القروب أو القناة التي تصل منها رسالة للبوت.
    """

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in ("group", "supergroup", "channel"):
        return

    try:
        await asyncio.to_thread(_save_chat_sync, chat)
    except Exception:
        pass


# =========================================================
# تسجيل حالة البوت داخل القروب / القناة
# =========================================================

def _update_bot_chat_sync(chat, active):
    if not chat:
        return

    if chat.type not in ("group", "supergroup", "channel"):
        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            f"""
            UPDATE {SEND_CHATS_TABLE}
            SET
                title = %s,
                username = %s,
                chat_type = %s,
                active = %s
            WHERE chat_id = %s
            """,
            (
                chat.title or "",
                chat.username or "",
                chat.type,
                active,
                chat.id,
            ),
        )

        if cur.rowcount == 0 and active:
            cur.execute(
                f"""
                INSERT INTO {SEND_CHATS_TABLE}
                    (chat_id, chat_type, title, username, active)
                VALUES
                    (%s, %s, %s, %s, TRUE)
                """,
                (
                    chat.id,
                    chat.type,
                    chat.title or "",
                    chat.username or "",
                ),
            )

        conn.commit()

    finally:
        cur.close()
        conn.close()


async def track_bot_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يتابع دخول/خروج البوت من القروبات والقنوات.
    """

    member_update = update.my_chat_member

    if not member_update:
        return

    chat = member_update.chat

    if chat.type not in ("group", "supergroup", "channel"):
        return

    new_status = member_update.new_chat_member.status

    active = new_status in (
        "member",
        "administrator",
        "creator",
    )

    try:
        await asyncio.to_thread(
            _update_bot_chat_sync,
            chat,
            active,
        )
    except Exception:
        pass


# =========================================================
# جلب القروبات والقنوات
# =========================================================

def _get_active_chats_sync():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            f"""
            SELECT chat_id, chat_type, title, username
            FROM {SEND_CHATS_TABLE}
            WHERE active = TRUE
            ORDER BY chat_id
            """
        )

        rows = cur.fetchall()

        return rows

    finally:
        cur.close()
        conn.close()


async def get_active_chats():
    return await asyncio.to_thread(_get_active_chats_sync)


# =========================================================
# UTF-16
# =========================================================

def _utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


# =========================================================
# استخراج المتغيرات
# =========================================================

PRIVATE_VARIABLES = {
    "#الاسم",
    "#منشن",
    "#يوزره",
    "#اليوزر",
    "#الرسائل",
    "#الايدي",
    "#الرتبه",
    "#التعديل",
    "#النقاط",
}

GROUP_VARIABLES = {
    "#الاسم",
    "#منشن",
}


def _get_private_replacements(user, user_data):
    username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )

    messages = 0
    rank = "عضو"
    points = 0

    if user_data:
        messages = user_data.get("messages", 0) or 0
        rank = user_data.get("rank", "عضو") or "عضو"
        points = user_data.get("points", 0) or 0

    return {
        "#الاسم": user.first_name or "مستخدم",
        "#منشن": user.first_name or "مستخدم",
        "#يوزره": username,
        "#اليوزر": username,
        "#الرسائل": str(messages),
        "#الايدي": str(user.id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points),
    }


def _get_group_replacements(chat):
    title = chat.title or "المجموعة"

    return {
        "#الاسم": title,
        "#منشن": title,
    }


# =========================================================
# تجهيز النص + الـ Entities
# =========================================================

def _replace_variables(
    text,
    entities,
    replacements,
    mention_user=None,
):
    if not text:
        return text, entities or []

    entities = entities or []

    occurrences = []

    for key, value in replacements.items():

        start_search = 0

        while True:
            index = text.find(key, start_search)

            if index == -1:
                break

            old_start = _utf16_length(text[:index])
            old_length = _utf16_length(key)
            new_length = _utf16_length(value)

            occurrences.append(
                {
                    "start": old_start,
                    "end": old_start + old_length,
                    "old_length": old_length,
                    "new_length": new_length,
                    "key": key,
                    "value": value,
                }
            )

            start_search = index + len(key)

    if not occurrences:
        return text, entities

    occurrences.sort(key=lambda x: x["start"])

    # -----------------------------------------------------
    # بناء النص الجديد
    # -----------------------------------------------------

    result_parts = []

    last_index = 0

    for occurrence in occurrences:

        # نحول UTF-16 offset إلى Python index
        # بالاعتماد على النص الأصلي.
        old_start_utf16 = occurrence["start"]

        current_utf16 = 0
        python_index = 0

        for i, char in enumerate(text):
            char_len = _utf16_length(char)

            if current_utf16 >= old_start_utf16:
                python_index = i
                break

            current_utf16 += char_len

        else:
            python_index = len(text)

        result_parts.append(text[last_index:python_index])
        result_parts.append(occurrence["value"])

        last_index = python_index + len(occurrence["key"])

    result_parts.append(text[last_index:])

    final_text = "".join(result_parts)

    # -----------------------------------------------------
    # تعديل الـ Entities القديمة
    # -----------------------------------------------------

    final_entities = []

    for old_entity in entities:

        old_offset = old_entity.offset or 0
        old_length = old_entity.length or 0
        old_end = old_offset + old_length

        new_offset = old_offset
        new_length = old_length

        for occurrence in occurrences:

            start = occurrence["start"]
            end = occurrence["end"]

            difference = (
                occurrence["new_length"]
                - occurrence["old_length"]
            )

            # المتغير قبل الـ entity
            if end <= old_offset:
                new_offset += difference

            # المتغير داخل الـ entity
            elif (
                start >= old_offset
                and end <= old_end
            ):
                new_length += difference

        try:
            new_entity = MessageEntity(
                type=old_entity.type,
                offset=new_offset,
                length=new_length,
                url=old_entity.url,
                user=old_entity.user,
                language=old_entity.language,
                custom_emoji_id=old_entity.custom_emoji_id,
            )

            final_entities.append(new_entity)

        except Exception:
            final_entities.append(old_entity)

    # -----------------------------------------------------
    # #منشن حقيقي في الخاص
    # -----------------------------------------------------

    if mention_user:

        for occurrence in occurrences:

            if occurrence["key"] != "#منشن":
                continue

            new_offset = occurrence["start"]

            for previous in occurrences:

                if previous is occurrence:
                    break

                if previous["end"] <= occurrence["start"]:
                    new_offset += (
                        previous["new_length"]
                        - previous["old_length"]
                    )

            mention_entity = MessageEntity(
                type="text_mention",
                offset=new_offset,
                length=_utf16_length(
                    occurrence["value"]
                ),
                user=mention_user,
            )

            final_entities.append(
                mention_entity
            )

    return final_text, final_entities


# =========================================================
# تجهيز الرسالة للخاص
# =========================================================

async def _prepare_private_content(message, user):
    user_data = await get_user_data(user.id)

    replacements = _get_private_replacements(
        user,
        user_data,
    )

    # نص
    if message.text is not None:

        text, entities = _replace_variables(
            message.text,
            message.entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "text",
            "text": text,
            "entities": entities,
        }

    # صورة
    if message.photo:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # فيديو
    if message.video:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Animation / GIF
    if message.animation:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "animation",
            "file_id": message.animation.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Sticker
    if message.sticker:

        return {
            "type": "sticker",
            "file_id": message.sticker.file_id,
        }

    # Voice
    if message.voice:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "voice",
            "file_id": message.voice.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Audio
    if message.audio:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "audio",
            "file_id": message.audio.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Document
    if message.document:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
            mention_user=user,
        )

        return {
            "type": "document",
            "file_id": message.document.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Video note لا يحتوي caption
    if message.video_note:

        return {
            "type": "video_note",
            "file_id": message.video_note.file_id,
        }

    # Location
    if message.location:

        return {
            "type": "location",
            "latitude": message.location.latitude,
            "longitude": message.location.longitude,
        }

    # Contact
    if message.contact:

        return {
            "type": "contact",
            "phone_number": message.contact.phone_number,
            "first_name": message.contact.first_name,
            "last_name": message.contact.last_name or "",
            "vcard": message.contact.vcard,
        }

    return None


# =========================================================
# تجهيز الرسالة للقروب / القناة
# =========================================================

def _prepare_group_content(message, chat):
    replacements = _get_group_replacements(chat)

    # نص
    if message.text is not None:

        text, entities = _replace_variables(
            message.text,
            message.entities,
            replacements,
        )

        return {
            "type": "text",
            "text": text,
            "entities": entities,
        }

    # صورة
    if message.photo:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
        )

        return {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # فيديو
    if message.video:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
        )

        return {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Animation
    if message.animation:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
        )

        return {
            "type": "animation",
            "file_id": message.animation.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Sticker
    if message.sticker:

        return {
            "type": "sticker",
            "file_id": message.sticker.file_id,
        }

    # Voice
    if message.voice:

        return {
            "type": "voice",
            "file_id": message.voice.file_id,
        }

    # Audio
    if message.audio:

        return {
            "type": "audio",
            "file_id": message.audio.file_id,
        }

    # Document
    if message.document:

        caption = message.caption or ""

        caption, entities = _replace_variables(
            caption,
            message.caption_entities,
            replacements,
        )

        return {
            "type": "document",
            "file_id": message.document.file_id,
            "caption": caption,
            "caption_entities": entities,
        }

    # Video note
    if message.video_note:

        return {
            "type": "video_note",
            "file_id": message.video_note.file_id,
        }

    # Location
    if message.location:

        return {
            "type": "location",
            "latitude": message.location.latitude,
            "longitude": message.location.longitude,
        }

    # Contact
    if message.contact:

        return {
            "type": "contact",
            "phone_number": message.contact.phone_number,
            "first_name": message.contact.first_name,
            "last_name": message.contact.last_name or "",
            "vcard": message.contact.vcard,
        }

    return None


# =========================================================
# إرسال المحتوى
# =========================================================

async def _send_prepared_content(
    bot,
    chat_id,
    content,
    reply_markup=None,
):
    if not content:
        return

    content_type = content["type"]

    if content_type == "text":

        await bot.send_message(
            chat_id=chat_id,
            text=content["text"],
            entities=content["entities"] or None,
            reply_markup=reply_markup,
        )

    elif content_type == "photo":

        await bot.send_photo(
            chat_id=chat_id,
            photo=content["file_id"],
            caption=content["caption"] or None,
            caption_entities=(
                content["caption_entities"]
                or None
            ),
            reply_markup=reply_markup,
        )

    elif content_type == "video":

        await bot.send_video(
            chat_id=chat_id,
            video=content["file_id"],
            caption=content["caption"] or None,
            caption_entities=(
                content["caption_entities"]
                or None
            ),
            reply_markup=reply_markup,
        )

    elif content_type == "animation":

        await bot.send_animation(
            chat_id=chat_id,
            animation=content["file_id"],
            caption=content["caption"] or None,
            caption_entities=(
                content["caption_entities"]
                or None
            ),
            reply_markup=reply_markup,
        )

    elif content_type == "sticker":

        await bot.send_sticker(
            chat_id=chat_id,
            sticker=content["file_id"],
        )

    elif content_type == "voice":

        await bot.send_voice(
            chat_id=chat_id,
            voice=content["file_id"],
            caption=content.get("caption") or None,
            caption_entities=(
                content.get("caption_entities")
                or None
            ),
        )

    elif content_type == "audio":

        await bot.send_audio(
            chat_id=chat_id,
            audio=content["file_id"],
            caption=content.get("caption") or None,
            caption_entities=(
                content.get("caption_entities")
                or None
            ),
        )

    elif content_type == "document":

        await bot.send_document(
            chat_id=chat_id,
            document=content["file_id"],
            caption=content["caption"] or None,
            caption_entities=(
                content["caption_entities"]
                or None
            ),
            reply_markup=reply_markup,
        )

    elif content_type == "video_note":

        await bot.send_video_note(
            chat_id=chat_id,
            video_note=content["file_id"],
        )

    elif content_type == "location":

        await bot.send_location(
            chat_id=chat_id,
            latitude=content["latitude"],
            longitude=content["longitude"],
        )

    elif content_type == "contact":

        await bot.send_contact(
            chat_id=chat_id,
            phone_number=content["phone_number"],
            first_name=content["first_name"],
            last_name=content["last_name"] or None,
            vcard=content.get("vcard"),
        )


# =========================================================
# حذف رسالة /send
# =========================================================

async def _delete_command_message(update):
    message = update.effective_message

    if not message:
        return

    try:
        await message.delete()
    except Exception:
        pass


# =========================================================
# استخراج رسالة /send
# =========================================================

def _extract_send_message(message):
    text = message.text or message.caption

    if not text:
        return None

    match = re.match(
        r"^/send(?:@[A-Za-z0-9_]+)?\s+",
        text,
        flags=re.DOTALL,
    )

    if not match:
        return None

    prefix_length = match.end()

    # الرسالة الأصلية بعد /send
    payload = text[prefix_length:]

    if not payload:
        return None

    return {
        "text": payload,
        "prefix_length": prefix_length,
    }


# =========================================================
# نسخ الـ entities للجزء بعد /send
# =========================================================

def _get_payload_entities(
    entities,
    prefix_text,
):
    if not entities:
        return []

    prefix_length = _utf16_length(prefix_text)

    result = []

    for entity in entities:

        offset = entity.offset or 0
        length = entity.length or 0
        end = offset + length

        # entity بالكامل قبل الرسالة
        if end <= prefix_length:
            continue

        # entity يبدأ قبل الرسالة
        if offset < prefix_length:
            new_offset = 0
            new_length = end - prefix_length
        else:
            new_offset = offset - prefix_length
            new_length = length

        if new_length <= 0:
            continue

        try:
            result.append(
                MessageEntity(
                    type=entity.type,
                    offset=new_offset,
                    length=new_length,
                    url=entity.url,
                    user=entity.user,
                    language=entity.language,
                    custom_emoji_id=entity.custom_emoji_id,
                )
            )
        except Exception:
            pass

    return result


# =========================================================
# إنشاء رسالة payload مؤقتة
# =========================================================

def _build_payload_message(message):
    extracted = _extract_send_message(message)

    if not extracted:
        return None

    prefix_length = extracted["prefix_length"]
    full_text = message.text or message.caption

    payload = extracted["text"]

    prefix_text = full_text[:prefix_length]

    if message.text is not None:

        entities = _get_payload_entities(
            message.entities,
            prefix_text,
        )

        # الرسالة النصية نفسها لا يمكن تعديلها مباشرة،
        # لذلك نعيد المعلومات المطلوبة فقط.
        return {
            "kind": "text",
            "text": payload,
            "entities": entities,
        }

    if message.photo:

        entities = _get_payload_entities(
            message.caption_entities,
            prefix_text,
        )

        return {
            "kind": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": payload,
            "caption_entities": entities,
        }

    if message.video:

        entities = _get_payload_entities(
            message.caption_entities,
            prefix_text,
        )

        return {
            "kind": "video",
            "file_id": message.video.file_id,
            "caption": payload,
            "caption_entities": entities,
        }

    if message.animation:

        entities = _get_payload_entities(
            message.caption_entities,
            prefix_text,
        )

        return {
            "kind": "animation",
            "file_id": message.animation.file_id,
            "caption": payload,
            "caption_entities": entities,
        }

    return {
        "kind": "text",
        "text": payload,
        "entities": [],
    }


# =========================================================
# إرسال /send في القروب
# =========================================================

async def _send_to_current_group(
    update,
    context,
    payload,
):
    chat = update.effective_chat

    # نعيد بناء رسالة content حسب القروب الحالي.
    if payload["kind"] == "text":

        text, entities = _replace_variables(
            payload["text"],
            payload["entities"],
            _get_group_replacements(chat),
        )

        await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            entities=entities or None,
        )

        return

    if payload["kind"] == "photo":

        caption, entities = _replace_variables(
            payload["caption"],
            payload["caption_entities"],
            _get_group_replacements(chat),
        )

        await context.bot.send_photo(
            chat_id=chat.id,
            photo=payload["file_id"],
            caption=caption or None,
            caption_entities=entities or None,
        )

        return

    if payload["kind"] == "video":

        caption, entities = _replace_variables(
            payload["caption"],
            payload["caption_entities"],
            _get_group_replacements(chat),
        )

        await context.bot.send_video(
            chat_id=chat.id,
            video=payload["file_id"],
            caption=caption or None,
            caption_entities=entities or None,
        )

        return

    if payload["kind"] == "animation":

        caption, entities = _replace_variables(
            payload["caption"],
            payload["caption_entities"],
            _get_group_replacements(chat),
        )

        await context.bot.send_animation(
            chat_id=chat.id,
            animation=payload["file_id"],
            caption=caption or None,
            caption_entities=entities or None,
        )


# =========================================================
# /send
# =========================================================

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    payload = _build_payload_message(message)

    # /send بدون رسالة
    if not payload:
        try:
            await message.delete()
        except Exception:
            pass

        return

    # -----------------------------------------------------
    # نحذف الأمر أولًا
    # -----------------------------------------------------

    await _delete_command_message(update)

    # -----------------------------------------------------
    # داخل قروب / قناة
    # -----------------------------------------------------

    if chat.type in ("group", "supergroup", "channel"):

        try:
            await _send_to_current_group(
                update,
                context,
                payload,
            )
        except Exception:
            pass

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # داخل الخاص
    # -----------------------------------------------------

    if chat.type == "private":

        chats = await get_active_chats()

        if not chats:
            raise ApplicationHandlerStop

        success = 0

        for (
            chat_id,
            chat_type,
            title,
            username,
        ) in chats:

            try:
                target_chat = await context.bot.get_chat(
                    chat_id
                )

                if payload["kind"] == "text":

                    text, entities = _replace_variables(
                        payload["text"],
                        payload["entities"],
                        _get_group_replacements(
                            target_chat
                        ),
                    )

                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        entities=entities or None,
                    )

                elif payload["kind"] == "photo":

                    caption, entities = _replace_variables(
                        payload["caption"],
                        payload["caption_entities"],
                        _get_group_replacements(
                            target_chat
                        ),
                    )

                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=payload["file_id"],
                        caption=caption or None,
                        caption_entities=(
                            entities or None
                        ),
                    )

                elif payload["kind"] == "video":

                    caption, entities = _replace_variables(
                        payload["caption"],
                        payload["caption_entities"],
                        _get_group_replacements(
                            target_chat
                        ),
                    )

                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=payload["file_id"],
                        caption=caption or None,
                        caption_entities=(
                            entities or None
                        ),
                    )

                elif payload["kind"] == "animation":

                    caption, entities = _replace_variables(
                        payload["caption"],
                        payload["caption_entities"],
                        _get_group_replacements(
                            target_chat
                        ),
                    )

                    await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=payload["file_id"],
                        caption=caption or None,
                        caption_entities=(
                            entities or None
                        ),
                    )

                elif payload["kind"] == "text":
                    pass

                success += 1

            except Exception:
                # إذا البوت خرج من القروب/القناة
                # نعطّلها من القائمة.
                try:
                    if chat_type in (
                        "group",
                        "supergroup",
                        "channel",
                    ):
                        await asyncio.to_thread(
                            _mark_chat_inactive,
                            chat_id,
                        )
                except Exception:
                    pass

        raise ApplicationHandlerStop


# =========================================================
# تعطيل قروب / قناة
# =========================================================

def _mark_chat_inactive(chat_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            f"""
            UPDATE {SEND_CHATS_TABLE}
            SET active = FALSE
            WHERE chat_id = %s
            """,
            (chat_id,),
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


# =========================================================
# حذف أي رسالة تبدأ بـ /
# =========================================================

async def delete_slash_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    يحذف أي رسالة تبدأ بـ /
    بشرط أن يكون بعدها نص.

    مثال:
        /start
        /help
        /هلا
        /send هلا

    لكن:
        /
    لا يتم حذفها.

    لا نستخدم ApplicationHandlerStop هنا،
    حتى تستمر الأوامر الأخرى بالعمل.
    """

    message = update.effective_message

    if not message:
        return

    text = message.text or message.caption

    if not text:
        return

    # لازم يبدأ بـ /
    if not text.startswith("/"):
        return

    # "/" فقط تبقى
    if text.strip() == "/":
        return

    # نتأكد أن هناك شيئًا بعد /
    if len(text.strip()) <= 1:
        return

    # نحذف الرسالة فقط
    try:
        await message.delete()
    except Exception:
        pass

    # مهم جدًا:
    # لا نوقف تنفيذ الأمر.
    return
