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
    """
    يستبدل متغيرات الستارت ويصحح مواقع MessageEntity
    بعد تغير طول النص.
    """

    replacements = _get_start_replacements(
        user,
        user_data
    )

    # نحتفظ بمعلومات كل استبدال في النص القديم
    replacements_info = []

    final_text = original_text

    # نبحث عن كل المتغيرات الموجودة فعليًا
    for key, value in replacements.items():

        start = 0

        while True:
            position = original_text.find(
                key,
                start
            )

            if position == -1:
                break

            replacements_info.append({
                "start": position,
                "end": position + len(key),
                "old_length": _utf16_length(key),
                "new_length": _utf16_length(value),
            })

            start = position + len(key)

        final_text = final_text.replace(
            key,
            value
        )

    # ترتيب الاستبدالات حسب موقعها في النص الأصلي
    replacements_info.sort(
        key=lambda item: item["start"]
    )

    entities = []

    for entity_data in raw_entities:
        entity = MessageEntity.de_json(
            entity_data
        )

        if not entity:
            continue

        old_offset = entity.offset or 0
        old_length = entity.length or 0

        new_offset = old_offset

        # تعديل الـ offset حسب المتغيرات الموجودة قبله
        for replacement in replacements_info:

            replacement_start_utf16 = _utf16_length(
                original_text[
                    :replacement["start"]
                ]
            )

            if replacement_start_utf16 < old_offset:
                difference = (
                    replacement["new_length"]
                    - replacement["old_length"]
                )

                new_offset += difference

        entity.offset = new_offset

        # إذا كانت الـ entity نفسها تغطي متغيرًا،
        # نحاول تعديل طولها أيضًا.
        old_end = old_offset + old_length
        new_length = old_length

        for replacement in replacements_info:

            replacement_start_utf16 = _utf16_length(
                original_text[
                    :replacement["start"]
                ]
            )

            replacement_end_utf16 = (
                replacement_start_utf16
                + replacement["old_length"]
            )

            if (
                replacement_start_utf16 >= old_offset
                and replacement_end_utf16 <= old_end
            ):
                new_length += (
                    replacement["new_length"]
                    - replacement["old_length"]
                )

        entity.length = new_length

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

    # قراءة الـ entities المحفوظة
    try:
        raw_entities = json.loads(
            entities_json or "[]"
        )

    except Exception:
        raw_entities = []

    # استبدال المتغيرات مع تصحيح أماكن التنسيقات
    try:
        final_text, entities = (
            _build_start_text_and_entities(
                message_text,
                raw_entities,
                user,
                user_data
            )
        )

    except Exception:
        # في حال وجود entity قديمة أو تالفة،
        # لا نخلي /start يتعطل بالكامل.
        final_text = _replace_start_variables(
            message_text,
            user,
            user_data
        )

        entities = []

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
