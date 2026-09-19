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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تجاهل Deep Links مثل:
    # /start commands
    # /start whisper_xxx
    if context.args:
        return
    user = update.effective_user
    chat_id = update.effective_chat.id
    message_text, entities_json, images, buttons = await _get_start_data()
    # إذا ما فيه رسالة مخصصة
    if not message_text:
        message_text = (
            f"حياك الله {user.first_name} 🤍\n"
            "في البوت الجديد ⭐"
        )
        entities_json = "[]"
    # جلب بيانات المستخدم من الكاش
    user_data = await get_user_data(user.id)
    # استبدال المتغيرات
    final_text = _replace_start_variables(
        message_text,
        user,
        user_data
    )
    # إنشاء الأزرار
    reply_markup = _build_start_keyboard(buttons)
    # استرجاع تنسيقات Telegram
    entities = []
    try:
        import json
        raw_entities = json.loads(
            entities_json or "[]"
        )
        for entity_data in raw_entities:
            entity = MessageEntity.de_json(entity_data)
            if entity:
                entities.append(entity)
    except Exception:
        entities = []
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
