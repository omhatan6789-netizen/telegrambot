from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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


def _replace_start_variables(text, user, user_data):
    if not text:
        return text

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

    replacements = {
        "#الاسم": user.first_name or "مستخدم",
        "#يوزره": username,
        "#اليوزر": username,
        "#الرسائل": str(messages),
        "#الايدي": str(user.id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points),
    }

    for key, value in replacements.items():
        text = text.replace(key, value)

    return text


def _build_start_keyboard(buttons):
    if not buttons:
        return None

    rows = []

    for button_text, button_url in buttons:
        rows.append([
            InlineKeyboardButton(
                text=button_text,
                url=button_url
            )
        ])

    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # أي Deep Link مثل:
    # /start commands
    # /start whisper_xxx
    # لا يدخل في رسالة الستارت العادية.
    if context.args:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id

    message_text, entities_json, images, buttons = await _get_start_data()

    # إذا لم يتم إعداد ستارت مخصص، نستخدم الستارت القديم.
    if not message_text:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"حياك الله {user.first_name} 🤍\n"
                "في البوت الجديد ⭐"
            )
        )
        return

    user_data = get_user_data(user.id)

    final_text = _replace_start_variables(
        message_text,
        user,
        user_data
    )

    reply_markup = _build_start_keyboard(buttons)

    # نحاول إعادة الكيانات المحفوظة.
    entities = []

    try:
        import json
        from telegram import MessageEntity

        raw_entities = json.loads(entities_json or "[]")

        for entity_data in raw_entities:
            entity = MessageEntity.de_json(entity_data)
            if entity:
                entities.append(entity)

    except Exception:
        entities = []

    # إذا توجد صور:
    # ترسل كلها مع بعض، ثم رسالة الستارت تحتها.
    if images:
        media = []

        for index, image in enumerate(images):
            media.append(
                __import__("telegram").InputMediaPhoto(
                    media=image[1]
                )
            )

        try:
            await context.bot.send_media_group(
                chat_id=chat_id,
                media=media
            )
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=final_text,
        entities=entities or None,
        reply_markup=reply_markup
    )
