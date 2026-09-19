import json

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MessageEntity,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes

from database import connect
from handlers.cache import get_user_data


async def _get_start_data():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT message_text, message_entities
            FROM start_settings
            WHERE id = 1
        """)

        row = cur.fetchone()

        cur.execute("""
            SELECT id, file_id
            FROM start_images
            ORDER BY image_order ASC, id ASC
        """)

        images = cur.fetchall()

        cur.execute("""
            SELECT button_text, button_url
            FROM start_buttons
            ORDER BY button_order ASC, id ASC
        """)

        buttons = cur.fetchall()

        if not row:
            return None, "[]", images, buttons

        return row[0], row[1] or "[]", images, buttons

    finally:
        cur.close()
        conn.close()


def _get_start_replacements(user, user_data):
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
        "#يوزره": username,
        "#اليوزر": username,
        "#الرسائل": str(messages),
        "#الايدي": str(user.id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points),
    }


def _replace_start_variables(text, user, user_data):
    if not text:
        return text

    replacements = _get_start_replacements(
        user,
        user_data
    )

    for key, value in replacements.items():
        text = text.replace(key, value)

    return text


def _utf16_length(text):
    return len(
        text.encode("utf-16-le")
    ) // 2


def _build_start_text_and_entities(
    original_text,
    raw_entities,
    user,
    user_data
):
    replacements = _get_start_replacements(
        user,
        user_data
    )

    if not original_text:
        return original_text, []

    # نبني النص الجديد مع معرفة:
    # كل مكان من النص القديم أين أصبح في النص الجديد.
    parts = []
    position_map = []

    old_position = 0
    new_position = 0

    while old_position < len(original_text):
        matched_key = None

        for key in replacements:
            if original_text.startswith(
                key,
                old_position
            ):
                matched_key = key
                break

        if matched_key is not None:
            value = replacements[matched_key]

            parts.append(value)

            old_length = len(matched_key)
            new_length = len(value)

            for index in range(old_length):
                if new_length:
                    mapped = min(
                        index,
                        new_length - 1
                    )
                    position_map.append(
                        new_position + mapped
                    )
                else:
                    position_map.append(
                        new_position
                    )

            old_position += old_length
            new_position += new_length

        else:
            char = original_text[old_position]

            parts.append(char)

            position_map.append(
                new_position
            )

            old_position += 1
            new_position += 1

    final_text = "".join(parts)

    entities = []

    for entity_data in raw_entities:
        entity = MessageEntity.de_json(
            entity_data
        )

        if not entity:
            continue

        old_offset_utf16 = entity.offset or 0
        old_length_utf16 = entity.length or 0

        # نحول UTF-16 إلى Python index
        old_offset = 0
        old_units = 0

        for index, char in enumerate(original_text):
            char_units = _utf16_length(char)

            if old_units >= old_offset_utf16:
                old_offset = index
                break

            old_units += char_units

        else:
            old_offset = len(original_text)

        old_end_utf16 = (
            old_offset_utf16 +
            old_length_utf16
        )

        old_end = len(original_text)
        current_units = 0

        for index, char in enumerate(original_text):
            char_units = _utf16_length(char)

            if current_units >= old_end_utf16:
                old_end = index
                break

            current_units += char_units

        if old_end < old_offset:
            continue

        if old_offset >= len(position_map):
            continue

        new_offset = position_map[old_offset]

        if old_end > 0 and old_end - 1 < len(position_map):
            new_end = (
                position_map[old_end - 1]
                + len(
                    final_text[
                        position_map[old_end - 1]:
                        position_map[old_end - 1] + 1
                    ].encode("utf-16-le")
                ) // 2
            )
        else:
            new_end = new_offset

        # نحول Python index الجديد إلى UTF-16 offset
        new_offset_utf16 = _utf16_length(
            final_text[:new_offset]
        )

        new_length_utf16 = (
            _utf16_length(
                final_text[
                    new_offset:new_end
                ]
            )
        )

        entity.offset = new_offset_utf16
        entity.length = new_length_utf16

        if entity.length > 0:
            entities.append(entity)

    return final_text, entities


def _build_start_keyboard(buttons):
    if not buttons:
        return None

    rows = []

    # كل زرين في صف واحد
    for i in range(0, len(buttons), 2):
        row = []

        for button_text, button_url in buttons[i:i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=button_text,
                    url=button_url
                )
            )

        rows.append(row)

    return InlineKeyboardMarkup(rows)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    # تجاهل Deep Links مثل:
    # /start commands
    # /start whisper_xxx
    if context.args:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id

    message_text, entities_json, images, buttons = (
        await _get_start_data()
    )

    # إذا ما فيه رسالة مخصصة
    if not message_text:
        message_text = (
            f"حياك الله {user.first_name} 🤍\n"
            "في البوت الجديد ⭐"
        )
        entities_json = "[]"

    # جلب بيانات المستخدم من الكاش
    user_data = await get_user_data(
        user.id
    )

    # قراءة الـ entities الأصلية
    try:
        raw_entities = json.loads(
            entities_json or "[]"
        )
    except Exception:
        raw_entities = []

    # استبدال المتغيرات مع إصلاح أماكن التنسيقات
    final_text, entities = (
        _build_start_text_and_entities(
            message_text,
            raw_entities,
            user,
            user_data
        )
    )

    # إنشاء الأزرار
    reply_markup = _build_start_keyboard(
        buttons
    )

    # ==================================================
    # صورة واحدة
    # ==================================================

    if len(images) == 1:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=images[0][1],
            caption=final_text,
            caption_entities=entities or None,
            reply_markup=reply_markup
        )

        return

    # ==================================================
    # أكثر من صورة
    # ==================================================

    if len(images) > 1:
        media = []

        for index, image in enumerate(images):

            # وضع الكابشن على آخر صورة
            if index == len(images) - 1:
                media.append(
                    InputMediaPhoto(
                        media=image[1],
                        caption=final_text,
                        caption_entities=entities or None
                    )
                )

            else:
                media.append(
                    InputMediaPhoto(
                        media=image[1]
                    )
                )

        await context.bot.send_media_group(
            chat_id=chat_id,
            media=media
        )

        # Telegram لا يسمح بوضع Inline Keyboard
        # مباشرة على Media Group.
        if reply_markup:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⠀",
                reply_markup=reply_markup
            )

        return

    # ==================================================
    # بدون صورة
    # ==================================================

    await context.bot.send_message(
        chat_id=chat_id,
        text=final_text,
        entities=entities or None,
        reply_markup=reply_markup
    )
