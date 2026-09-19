import json
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import connect


OWNER_ID = 8453977662

sessions = {}


# =========================================================
# التحقق من صلاحية الوصول
# =========================================================

def _is_allowed(user):
    if not user:
        return False

    if user.id == OWNER_ID:
        return True

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT 1
            FROM start_access
            WHERE user_id = ?
               OR (
                    username IS NOT NULL
                    AND username = ?
               )
            LIMIT 1
            """,
            (
                user.id,
                user.username.lower()
                if user.username
                else None
            )
        )

        return cur.fetchone() is not None

    finally:
        cur.close()
        conn.close()


# =========================================================
# القائمة الرئيسية
# =========================================================

def _main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "تعديل رسالة البدء",
                callback_data="startedit:message"
            ),
            InlineKeyboardButton(
                "اضافة ازرار",
                callback_data="startedit:buttons"
            )
        ],
        [
            InlineKeyboardButton(
                "المسموحين بالوصول",
                callback_data="startedit:access"
            ),
            InlineKeyboardButton(
                "اضافة صورة",
                callback_data="startedit:image"
            )
        ],
    ])


# =========================================================
# زر الرجوع للقائمة
# =========================================================

def _back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "↩️ الرجوع للقائمة",
                callback_data="startedit:menu"
            )
        ]
    ])


# =========================================================
# قائمة الأزرار
# =========================================================

def _buttons_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "اضف زر",
                callback_data="startedit:add_button"
            ),
            InlineKeyboardButton(
                "تعديل ترتيب زر",
                callback_data="startedit:order_button"
            )
        ],
        [
            InlineKeyboardButton(
                "حذف زر",
                callback_data="startedit:delete_button"
            ),
            InlineKeyboardButton(
                "↩️ الرجوع للقائمة",
                callback_data="startedit:menu"
            )
        ],
    ])


# =========================================================
# قائمة المسموحين
# =========================================================

async def _show_access(query):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, user_id, username
            FROM start_access
            ORDER BY id ASC
            """
        )

        rows = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    text = "المسموحين بالوصول:\n\n"

    if not rows:
        text += "لا يوجد أشخاص مضافين."

    else:
        for index, row in enumerate(rows, 1):
            if row[2]:
                text += f"{index}. @{row[2]}\n"
            else:
                text += f"{index}. {row[1]}\n"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "اضافة شخص",
                callback_data="startedit:access_add"
            ),
            InlineKeyboardButton(
                "حذف شخص",
                callback_data="startedit:access_delete"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ الرجوع للقائمة",
                callback_data="startedit:menu"
            )
        ]
    ])

    await query.edit_message_text(
        text,
        reply_markup=keyboard
    )


# =========================================================
# قائمة الصور
# =========================================================

async def _show_images(query):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, image_order
            FROM start_images
            ORDER BY image_order ASC, id ASC
            """
        )

        rows = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    text = (
        f"عدد صور الستارت الحالية: {len(rows)}\n\n"
        "تقدر تضيف صور متعددة، وعند استخدام /start "
        "ترسل الصور كلها مع بعض."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "اضف صورة",
                callback_data="startedit:image_add"
            ),
            InlineKeyboardButton(
                "حذف صورة",
                callback_data="startedit:image_delete"
            )
        ],
        [
            InlineKeyboardButton(
                "حذف كل الصور",
                callback_data="startedit:image_delete_all"
            ),
            InlineKeyboardButton(
                "↩️ الرجوع للقائمة",
                callback_data="startedit:menu"
            )
        ]
    ])

    await query.edit_message_text(
        text,
        reply_markup=keyboard
    )


# =========================================================
# أمر تعديل الستارت
# =========================================================

async def start_editor_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    if update.effective_chat.type != "private":
        return

    user = update.effective_user

    if not _is_allowed(user):
        raise ApplicationHandlerStop

    sessions.pop(user.id, None)

    await update.message.reply_text(
        "اهلًا بك عزيزي المطور 🎖️\n"
        "هذي قائمة تعديل الستارت❗️",
        reply_markup=_main_keyboard()
    )

    raise ApplicationHandlerStop


# =========================================================
# أزرار محرر الستارت
# =========================================================

async def start_editor_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    user = query.from_user

    if not _is_allowed(user):
        raise ApplicationHandlerStop

    data = query.data

    # -----------------------------------------------------
    # القائمة الرئيسية
    # -----------------------------------------------------

    if data == "startedit:menu":
        sessions.pop(user.id, None)

        await query.edit_message_text(
            "اهلًا بك عزيزي المطور 🎖️\n"
            "هذي قائمة تعديل الستارت❗️",
            reply_markup=_main_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # تعديل رسالة البدء
    # -----------------------------------------------------

    if data == "startedit:message":
        sessions[user.id] = {
            "action": "message"
        }

        await query.edit_message_text(
            "حسنًا ارسل الرسالة",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # قائمة الأزرار
    # -----------------------------------------------------

    if data == "startedit:buttons":
        sessions.pop(user.id, None)

        await query.edit_message_text(
            "اختر العملية التي تريدها:",
            reply_markup=_buttons_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # إضافة زر
    # -----------------------------------------------------

    if data == "startedit:add_button":
        sessions[user.id] = {
            "action": "button_text"
        }

        await query.edit_message_text(
            "حسنًا ارسل اسم الزر",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # تعديل ترتيب زر
    # -----------------------------------------------------

    if data == "startedit:order_button":

        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT id, button_text
                FROM start_buttons
                ORDER BY button_order ASC, id ASC
                """
            )

            buttons = cur.fetchall()

        finally:
            cur.close()
            conn.close()

        if not buttons:
            await query.edit_message_text(
                "ما فيه أزرار مضافة حاليًا.",
                reply_markup=_buttons_keyboard()
            )

            raise ApplicationHandlerStop

        text = "أزرارك الحالية:\n\n"

        for index, button in enumerate(buttons, 1):
            text += f"{index}. {button[1]}\n"

        text += "\nارسل رقم الزر الذي تريد تغيير ترتيبه:"

        sessions[user.id] = {
            "action": "order_select",
            "buttons": buttons
        }

        await query.edit_message_text(
            text,
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # حذف زر
    # -----------------------------------------------------

    if data == "startedit:delete_button":

        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT id, button_text
                FROM start_buttons
                ORDER BY button_order ASC, id ASC
                """
            )

            buttons = cur.fetchall()

        finally:
            cur.close()
            conn.close()

        if not buttons:
            await query.edit_message_text(
                "ما فيه أزرار مضافة حاليًا.",
                reply_markup=_buttons_keyboard()
            )

            raise ApplicationHandlerStop

        text = "أزرارك الحالية:\n\n"

        for index, button in enumerate(buttons, 1):
            text += f"{index}. {button[1]}\n"

        text += "\nارسل رقم الزر الذي تريد حذفه:"

        sessions[user.id] = {
            "action": "delete_button",
            "buttons": buttons
        }

        await query.edit_message_text(
            text,
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # المسموحين
    # -----------------------------------------------------

    if data == "startedit:access":

        if user.id != OWNER_ID:
            await query.answer(
                "لا يمكنك الدخول لهذا الزر 🚨",
                show_alert=True
            )
            raise ApplicationHandlerStop

        sessions.pop(user.id, None)

        await _show_access(query)

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # الصور
    # -----------------------------------------------------

    if data == "startedit:image":
        sessions.pop(user.id, None)

        await _show_images(query)

        raise ApplicationHandlerStop


# =========================================================
# رسائل محرر الستارت
# =========================================================

async def start_editor_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    if update.effective_chat.type != "private":
        return

    user = update.effective_user

    if not _is_allowed(user):
        return

    session = sessions.get(user.id)

    if not session:
        return

    action = session.get("action")

    if action == "message":
        await _save_start_message(update)
        raise ApplicationHandlerStop

    if action == "button_text":

        if not update.message.text:
            await update.message.reply_text(
                "ارسل اسم الزر كنص.",
                reply_markup=_back_keyboard()
            )

            raise ApplicationHandlerStop

        sessions[user.id] = {
            "action": "button_url",
            "button_text": update.message.text.strip()
        }

        await update.message.reply_text(
            "حسنًا، الآن ارسل الرابط أو يوزر التليجرام:\n\n"
            "مثال:\n"
            "https://example.com\n"
            "@username",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    if action == "button_url":
        await _save_button(update)
        raise ApplicationHandlerStop

    if action == "order_select":
        await _select_order_button(update)
        raise ApplicationHandlerStop

    if action == "order_position":
        await _save_button_order(update)
        raise ApplicationHandlerStop

    if action == "delete_button":
        await _delete_button(update)
        raise ApplicationHandlerStop

    if action == "access_add":

        if user.id != OWNER_ID:
            sessions.pop(user.id, None)
            return

        await _add_access(update)
        raise ApplicationHandlerStop

    if action == "access_delete":

        if user.id != OWNER_ID:
            sessions.pop(user.id, None)
            return

        await _delete_access(update)
        raise ApplicationHandlerStop

    if action == "image_add":
        await _add_image(update)
        raise ApplicationHandlerStop

    if action == "image_delete":
        await _delete_image(update)
        raise ApplicationHandlerStop


# =========================================================
# حفظ رسالة الستارت
# =========================================================

async def _save_start_message(update):
    message = update.message

    text = message.text or message.caption or ""

    if not text:
        await message.reply_text(
            "الرسالة ما تحتوي على نص أو كابشن.",
            reply_markup=_back_keyboard()
        )
        return

    entities = (
        message.entities
        if message.text
        else message.caption_entities
    ) or []

    entity_data = [
        entity.to_dict()
        for entity in entities
    ]

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE start_settings
            SET message_text = ?,
                message_entities = ?
            WHERE id = 1
            """,
            (
                text,
                json.dumps(
                    entity_data,
                    ensure_ascii=False
                )
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await message.reply_text(
        "تم تعديل رسالة البدء بنجاح ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# حفظ الزر
# =========================================================

async def _save_button(update):
    message = update.message

    if not message.text:
        await message.reply_text(
            "ارسل الرابط أو اليوزر كنص.",
            reply_markup=_back_keyboard()
        )
        return

    url = message.text.strip()

    if url.startswith("@"):
        username = url[1:].strip()

        if not username:
            await message.reply_text(
                "يوزر غير صحيح.",
                reply_markup=_back_keyboard()
            )
            return

        url = f"https://t.me/{username}"

    elif not re.match(
        r"^https?://",
        url,
        re.IGNORECASE
    ):
        await message.reply_text(
            "ارسل رابط يبدأ بـ https:// أو يوزر يبدأ بـ @",
            reply_markup=_back_keyboard()
        )
        return

    button_text = sessions[
        update.effective_user.id
    ]["button_text"]

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT COALESCE(MAX(button_order), 0)
            FROM start_buttons
            """
        )

        max_order = cur.fetchone()[0] or 0

        cur.execute(
            """
            INSERT INTO start_buttons
            (
                button_text,
                button_url,
                button_order
            )
            VALUES (?, ?, ?)
            """,
            (
                button_text,
                url,
                max_order + 1
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await message.reply_text(
        "تمت إضافة الزر بنجاح ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# اختيار زر للترتيب
# =========================================================

async def _select_order_button(update):
    try:
        number = int(
            update.message.text.strip()
        )

    except (ValueError, AttributeError):
        await update.message.reply_text(
            "ارسل رقم الزر فقط.",
            reply_markup=_back_keyboard()
        )
        return

    buttons = sessions[
        update.effective_user.id
    ].get("buttons", [])

    if number < 1 or number > len(buttons):
        await update.message.reply_text(
            "رقم الزر غير صحيح.",
            reply_markup=_back_keyboard()
        )
        return

    selected = buttons[number - 1]

    sessions[update.effective_user.id] = {
        "action": "order_position",
        "button_id": selected[0],
        "button_text": selected[1],
        "buttons": buttons
    }

    await update.message.reply_text(
        f"الزر المحدد: {selected[1]}\n\n"
        "ارسل الترتيب الجديد.\n"
        "مثال: 1",
        reply_markup=_back_keyboard()
    )


# =========================================================
# حفظ ترتيب الزر
# =========================================================

async def _save_button_order(update):
    try:
        new_position = int(
            update.message.text.strip()
        )

    except (ValueError, AttributeError):
        await update.message.reply_text(
            "ارسل رقم الترتيب فقط.",
            reply_markup=_back_keyboard()
        )
        return

    session = sessions[
        update.effective_user.id
    ]

    buttons = session["buttons"]

    if new_position < 1 or new_position > len(buttons):
        await update.message.reply_text(
            "الترتيب غير صحيح.",
            reply_markup=_back_keyboard()
        )
        return

    selected_id = session["button_id"]

    ordered = [
        button
        for button in buttons
        if button[0] != selected_id
    ]

    selected = next(
        button
        for button in buttons
        if button[0] == selected_id
    )

    ordered.insert(
        new_position - 1,
        selected
    )

    conn = connect()
    cur = conn.cursor()

    try:
        for index, button in enumerate(ordered, 1):
            cur.execute(
                """
                UPDATE start_buttons
                SET button_order = ?
                WHERE id = ?
                """,
                (
                    index,
                    button[0]
                )
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم تعديل ترتيب الزر بنجاح ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# حذف الزر
# =========================================================

async def _delete_button(update):
    try:
        number = int(
            update.message.text.strip()
        )

    except (ValueError, AttributeError):
        await update.message.reply_text(
            "ارسل رقم الزر فقط.",
            reply_markup=_back_keyboard()
        )
        return

    buttons = sessions[
        update.effective_user.id
    ]["buttons"]

    if number < 1 or number > len(buttons):
        await update.message.reply_text(
            "رقم الزر غير صحيح.",
            reply_markup=_back_keyboard()
        )
        return

    button_id = buttons[number - 1][0]

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            DELETE FROM start_buttons
            WHERE id = ?
            """,
            (button_id,)
        )

        cur.execute(
            """
            SELECT id
            FROM start_buttons
            ORDER BY button_order ASC, id ASC
            """
        )

        remaining = cur.fetchall()

        for index, row in enumerate(remaining, 1):
            cur.execute(
                """
                UPDATE start_buttons
                SET button_order = ?
                WHERE id = ?
                """,
                (
                    index,
                    row[0]
                )
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم حذف الزر بنجاح ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# إضافة صورة
# =========================================================

async def _add_image(update):
    message = update.message

    if not message.photo:
        await message.reply_text(
            "ارسل صورة.",
            reply_markup=_back_keyboard()
        )
        return

    file_id = message.photo[-1].file_id

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT COALESCE(MAX(image_order), 0)
            FROM start_images
            """
        )

        max_order = cur.fetchone()[0] or 0

        cur.execute(
            """
            INSERT INTO start_images
            (
                file_id,
                image_order
            )
            VALUES (?, ?)
            """,
            (
                file_id,
                max_order + 1
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await message.reply_text(
        "تمت إضافة الصورة بنجاح ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# حذف صورة
# =========================================================

async def _delete_image(update):
    try:
        number = int(
            update.message.text.strip()
        )

    except (ValueError, AttributeError):
        await update.message.reply_text(
            "ارسل رقم الصورة فقط.",
            reply_markup=_back_keyboard()
        )
        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id
            FROM start_images
            ORDER BY image_order ASC, id ASC
            """
        )

        images = cur.fetchall()

        if number < 1 or number > len(images):
            await update.message.reply_text(
                "رقم الصورة غير صحيح.",
                reply_markup=_back_keyboard()
            )
            return

        image_id = images[number - 1][0]

        cur.execute(
            """
            DELETE FROM start_images
            WHERE id = ?
            """,
            (image_id,)
        )

        cur.execute(
            """
            SELECT id
            FROM start_images
            ORDER BY image_order ASC, id ASC
            """
        )

        remaining = cur.fetchall()

        for index, row in enumerate(remaining, 1):
            cur.execute(
                """
                UPDATE start_images
                SET image_order = ?
                WHERE id = ?
                """,
                (
                    index,
                    row[0]
                )
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم حذف الصورة بنجاح ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# أزرار المسموحين والصور
# =========================================================

async def start_editor_special_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    user = query.from_user
    data = query.data

    # -----------------------------------------------------
    # حماية المسموحين — للمالك فقط
    # -----------------------------------------------------

    if data in (
        "startedit:access_add",
        "startedit:access_delete",
    ):
        if user.id != OWNER_ID:
            await query.answer(
                "لا يمكنك الدخول لهذا الزر 🚨",
                show_alert=True
            )
            raise ApplicationHandlerStop

    await query.answer()

    if not _is_allowed(user):
        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # إضافة شخص
    # -----------------------------------------------------

    if data == "startedit:access_add":
        sessions[user.id] = {
            "action": "access_add"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره.\n\n"
            "مثال:\n"
            "8453977662\n"
            "@username",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # حذف شخص
    # -----------------------------------------------------

    if data == "startedit:access_delete":
        sessions[user.id] = {
            "action": "access_delete"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره لحذفه.",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # إضافة صورة
    # -----------------------------------------------------

    if data == "startedit:image_add":
        sessions[user.id] = {
            "action": "image_add"
        }

        await query.edit_message_text(
            "ارسل الصورة.",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # حذف صورة
    # -----------------------------------------------------

    if data == "startedit:image_delete":

        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT id
                FROM start_images
                ORDER BY image_order ASC, id ASC
                """
            )

            images = cur.fetchall()

        finally:
            cur.close()
            conn.close()

        if not images:
            await query.edit_message_text(
                "ما فيه صور حاليًا.",
                reply_markup=_show_images_keyboard_fallback()
            )

            raise ApplicationHandlerStop

        sessions[user.id] = {
            "action": "image_delete"
        }

        await query.edit_message_text(
            "ارسل رقم الصورة التي تريد حذفها.",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # حذف كل الصور
    # -----------------------------------------------------

    if data == "startedit:image_delete_all":

        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                DELETE FROM start_images
                """
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

        sessions.pop(user.id, None)

        await query.edit_message_text(
            "تم حذف جميع صور الستارت ✅",
            reply_markup=_back_keyboard()
        )

        raise ApplicationHandlerStop


def _show_images_keyboard_fallback():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "اضف صورة",
                callback_data="startedit:image_add"
            ),
            InlineKeyboardButton(
                "حذف صورة",
                callback_data="startedit:image_delete"
            )
        ],
        [
            InlineKeyboardButton(
                "حذف كل الصور",
                callback_data="startedit:image_delete_all"
            ),
            InlineKeyboardButton(
                "↩️ الرجوع للقائمة",
                callback_data="startedit:menu"
            )
        ]
    ])


# =========================================================
# إضافة شخص للمسموحين
# =========================================================

async def _add_access(update):
    value = update.message.text.strip()

    conn = connect()
    cur = conn.cursor()

    try:
        if value.startswith("@"):
            username = value[1:].strip().lower()

            if not username:
                await update.message.reply_text(
                    "اليوزر غير صحيح.",
                    reply_markup=_back_keyboard()
                )
                return

            cur.execute(
                """
                INSERT INTO start_access
                (
                    username
                )
                VALUES (?)
                """,
                (username,)
            )

        else:
            try:
                user_id = int(value)

            except ValueError:
                await update.message.reply_text(
                    "ارسل أيدي صحيح أو يوزر يبدأ بـ @.",
                    reply_markup=_back_keyboard()
                )
                return

            cur.execute(
                """
                INSERT INTO start_access
                (
                    user_id
                )
                VALUES (?)
                """,
                (user_id,)
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تمت الإضافة إلى المسموحين بالوصول ✅",
        reply_markup=_back_keyboard()
    )


# =========================================================
# حذف شخص من المسموحين
# =========================================================

async def _delete_access(update):
    value = update.message.text.strip()

    conn = connect()
    cur = conn.cursor()

    try:
        if value.startswith("@"):
            username = value[1:].strip().lower()

            cur.execute(
                """
                DELETE FROM start_access
                WHERE username = ?
                """,
                (username,)
            )

        else:
            try:
                user_id = int(value)

            except ValueError:
                await update.message.reply_text(
                    "ارسل أيدي صحيح أو يوزر يبدأ بـ @.",
                    reply_markup=_back_keyboard()
                )
                return

            cur.execute(
                """
                DELETE FROM start_access
                WHERE user_id = ?
                """,
                (user_id,)
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم حذف الشخص من المسموحين ✅",
        reply_markup=_back_keyboard()
    )
