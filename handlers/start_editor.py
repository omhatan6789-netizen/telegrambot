import json
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from database import connect


OWNER_ID = 8453977662

sessions = {}


def _is_allowed(user):
    if not user:
        return False

    if user.id == OWNER_ID:
        return True

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 1
            FROM start_access
            WHERE user_id = ?
               OR (
                    username IS NOT NULL
                    AND username = ?
               )
            LIMIT 1
        """, (
            user.id,
            user.username.lower()
            if user.username
            else None
        ))

        return cur.fetchone() is not None

    finally:
        cur.close()
        conn.close()


def _main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "تعديل رسالة البدء",
                callback_data="startedit:message"
            )
        ],
        [
            InlineKeyboardButton(
                "اضافة ازرار",
                callback_data="startedit:buttons"
            )
        ],
        [
            InlineKeyboardButton(
                "المسموحين بالوصول",
                callback_data="startedit:access"
            )
        ],
        [
            InlineKeyboardButton(
                "اضافة صورة",
                callback_data="startedit:image"
            )
        ],
    ])


def _buttons_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "اضف زر",
                callback_data="startedit:add_button"
            )
        ],
        [
            InlineKeyboardButton(
                "تعديل ترتيب زر",
                callback_data="startedit:order_button"
            )
        ],
        [
            InlineKeyboardButton(
                "حذف زر",
                callback_data="startedit:delete_button"
            )
        ],
        [
            InlineKeyboardButton(
                "رجوع",
                callback_data="startedit:menu"
            )
        ],
    ])


async def start_editor_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_chat.type != "private":
        return

    user = update.effective_user

    if not _is_allowed(user):
        return

    await update.message.reply_text(
        "اهلًا بك عزيزي المطور 🎖️\n"
        "هذي قائمة تعديل الستارت❗️",
        reply_markup=_main_keyboard()
    )


async def start_editor_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if not _is_allowed(user):
        return

    data = query.data

    if data == "startedit:menu":
        await query.edit_message_text(
            "اهلًا بك عزيزي المطور 🎖️\n"
            "هذي قائمة تعديل الستارت❗️",
            reply_markup=_main_keyboard()
        )
        return

    if data == "startedit:message":
        sessions[user.id] = {
            "action": "message"
        }

        await query.edit_message_text(
            "حسنًا ارسل الرسالة"
        )
        return

    if data == "startedit:buttons":
        await query.edit_message_text(
            "اختر العملية التي تريدها:",
            reply_markup=_buttons_keyboard()
        )
        return

    if data == "startedit:add_button":
        sessions[user.id] = {
            "action": "button_text"
        }

        await query.edit_message_text(
            "ارسل اسم الزر:"
        )
        return

    if data == "startedit:order_button":
        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT id, button_text
                FROM start_buttons
                ORDER BY button_order ASC, id ASC
            """)
            buttons = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        if not buttons:
            await query.edit_message_text(
                "ما فيه أزرار مضافة حاليًا.",
                reply_markup=_buttons_keyboard()
            )
            return

        text = "أزرارك الحالية:\n\n"

        for index, button in enumerate(buttons, 1):
            text += f"{index}. {button[1]}\n"

        text += "\nارسل رقم الزر الذي تريد تغيير ترتيبه:"

        sessions[user.id] = {
            "action": "order_select",
            "buttons": buttons
        }

        await query.edit_message_text(text)
        return

    if data == "startedit:delete_button":
        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT id, button_text
                FROM start_buttons
                ORDER BY button_order ASC, id ASC
            """)
            buttons = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        if not buttons:
            await query.edit_message_text(
                "ما فيه أزرار مضافة حاليًا.",
                reply_markup=_buttons_keyboard()
            )
            return

        text = "أزرارك الحالية:\n\n"

        for index, button in enumerate(buttons, 1):
            text += f"{index}. {button[1]}\n"

        text += "\nارسل رقم الزر الذي تريد حذفه:"

        sessions[user.id] = {
            "action": "delete_button",
            "buttons": buttons
        }

        await query.edit_message_text(text)
        return

    if data == "startedit:access":
        await _show_access(query)
        return

    if data == "startedit:image":
        await _show_images(query)
        return


async def _show_access(query):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, user_id, username
            FROM start_access
            ORDER BY id ASC
        """)
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
            )
        ],
        [
            InlineKeyboardButton(
                "حذف شخص",
                callback_data="startedit:access_delete"
            )
        ],
        [
            InlineKeyboardButton(
                "رجوع",
                callback_data="startedit:menu"
            )
        ],
    ])

    await query.edit_message_text(
        text,
        reply_markup=keyboard
    )


async def _show_images(query):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, image_order
            FROM start_images
            ORDER BY image_order ASC, id ASC
        """)
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
            )
        ],
        [
            InlineKeyboardButton(
                "حذف صورة",
                callback_data="startedit:image_delete"
            )
        ],
        [
            InlineKeyboardButton(
                "حذف كل الصور",
                callback_data="startedit:image_delete_all"
            )
        ],
        [
            InlineKeyboardButton(
                "رجوع",
                callback_data="startedit:menu"
            )
        ],
    ])

    await query.edit_message_text(
        text,
        reply_markup=keyboard
    )


async def start_editor_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
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
        return

    if action == "button_text":
        if not update.message.text:
            await update.message.reply_text(
                "ارسل اسم الزر كنص."
            )
            return

        sessions[user.id] = {
            "action": "button_url",
            "button_text": update.message.text.strip()
        }

        await update.message.reply_text(
            "الآن ارسل الرابط أو يوزر التليجرام:\n\n"
            "مثال:\n"
            "https://example.com\n"
            "@username"
        )
        return

    if action == "button_url":
        await _save_button(update)
        return

    if action == "order_select":
        await _select_order_button(update)
        return

    if action == "order_position":
        await _save_button_order(update)
        return

    if action == "delete_button":
        await _delete_button(update)
        return

    if action == "access_add":
        await _add_access(update)
        return

    if action == "access_delete":
        await _delete_access(update)
        return

    if action == "image_add":
        await _add_image(update)
        return

    if action == "image_delete":
        await _delete_image(update)
        return


async def _save_start_message(update):
    message = update.message

    text = message.text or message.caption or ""

    if not text:
        await message.reply_text(
            "الرسالة ما تحتوي على نص أو كابشن."
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
        cur.execute("""
            UPDATE start_settings
            SET message_text = ?,
                message_entities = ?
            WHERE id = 1
        """, (
            text,
            json.dumps(
                entity_data,
                ensure_ascii=False
            )
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await message.reply_text(
        "تم تعديل رسالة البدء بنجاح ✅"
    )


async def _save_button(update):
    url = update.message.text.strip()

    if url.startswith("@"):
        username = url[1:].strip()

        if not username:
            await update.message.reply_text(
                "يوزر غير صحيح."
            )
            return

        url = f"https://t.me/{username}"

    elif not re.match(
        r"^https?://",
        url,
        re.IGNORECASE
    ):
        await update.message.reply_text(
            "ارسل رابط يبدأ بـ https:// أو يوزر يبدأ بـ @"
        )
        return

    button_text = sessions[
        update.effective_user.id
    ]["button_text"]

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT COALESCE(MAX(button_order), 0)
            FROM start_buttons
        """)

        max_order = cur.fetchone()[0] or 0

        cur.execute("""
            INSERT INTO start_buttons
            (
                button_text,
                button_url,
                button_order
            )
            VALUES (?, ?, ?)
        """, (
            button_text,
            url,
            max_order + 1
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تمت إضافة الزر بنجاح ✅"
    )


async def _select_order_button(update):
    try:
        number = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "ارسل رقم الزر فقط."
        )
        return

    buttons = sessions[
        update.effective_user.id
    ].get("buttons", [])

    if number < 1 or number > len(buttons):
        await update.message.reply_text(
            "رقم الزر غير صحيح."
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
        "مثال: 1"
    )


async def _save_button_order(update):
    try:
        new_position = int(
            update.message.text.strip()
        )
    except ValueError:
        await update.message.reply_text(
            "ارسل رقم الترتيب فقط."
        )
        return

    session = sessions[
        update.effective_user.id
    ]

    buttons = session["buttons"]

    if new_position < 1 or new_position > len(buttons):
        await update.message.reply_text(
            "الترتيب غير صحيح."
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
            cur.execute("""
                UPDATE start_buttons
                SET button_order = ?
                WHERE id = ?
            """, (
                index,
                button[0]
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم تعديل ترتيب الزر بنجاح ✅"
    )


async def _delete_button(update):
    try:
        number = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "ارسل رقم الزر فقط."
        )
        return

    buttons = sessions[
        update.effective_user.id
    ]["buttons"]

    if number < 1 or number > len(buttons):
        await update.message.reply_text(
            "رقم الزر غير صحيح."
        )
        return

    button_id = buttons[number - 1][0]

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE FROM start_buttons
            WHERE id = ?
        """, (button_id,))

        cur.execute("""
            SELECT id
            FROM start_buttons
            ORDER BY button_order ASC, id ASC
        """)

        remaining = cur.fetchall()

        for index, row in enumerate(remaining, 1):
            cur.execute("""
                UPDATE start_buttons
                SET button_order = ?
                WHERE id = ?
            """, (
                index,
                row[0]
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم حذف الزر بنجاح ✅"
    )


async def _add_image(update):
    message = update.message

    if not message.photo:
        await message.reply_text(
            "ارسل صورة."
        )
        return

    file_id = message.photo[-1].file_id

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT COALESCE(MAX(image_order), 0)
            FROM start_images
        """)

        max_order = cur.fetchone()[0] or 0

        cur.execute("""
            INSERT INTO start_images
            (
                file_id,
                image_order
            )
            VALUES (?, ?)
        """, (
            file_id,
            max_order + 1
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await message.reply_text(
        "تمت إضافة الصورة بنجاح ✅"
    )


async def _delete_image(update):
    try:
        number = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "ارسل رقم الصورة فقط."
        )
        return

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id
            FROM start_images
            ORDER BY image_order ASC, id ASC
        """)

        images = cur.fetchall()

        if number < 1 or number > len(images):
            await update.message.reply_text(
                "رقم الصورة غير صحيح."
            )
            return

        image_id = images[number - 1][0]

        cur.execute("""
            DELETE FROM start_images
            WHERE id = ?
        """, (image_id,))

        cur.execute("""
            SELECT id
            FROM start_images
            ORDER BY image_order ASC, id ASC
        """)

        remaining = cur.fetchall()

        for index, row in enumerate(remaining, 1):
            cur.execute("""
                UPDATE start_images
                SET image_order = ?
                WHERE id = ?
            """, (
                index,
                row[0]
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم حذف الصورة بنجاح ✅"
    )


async def start_editor_special_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if not _is_allowed(user):
        return

    data = query.data

    if data == "startedit:access_add":
        sessions[user.id] = {
            "action": "access_add"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره.\n\n"
            "مثال:\n"
            "8453977662\n"
            "@username"
        )
        return

    if data == "startedit:access_delete":
        sessions[user.id] = {
            "action": "access_delete"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره لحذفه."
        )
        return

    if data == "startedit:image_add":
        sessions[user.id] = {
            "action": "image_add"
        }

        await query.edit_message_text(
            "ارسل الصورة."
        )
        return

    if data == "startedit:image_delete":
        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT id
                FROM start_images
                ORDER BY image_order ASC, id ASC
            """)
            images = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        if not images:
            await query.edit_message_text(
                "ما فيه صور حاليًا."
            )
            return

        sessions[user.id] = {
            "action": "image_delete"
        }

        await query.edit_message_text(
            "ارسل رقم الصورة التي تريد حذفها."
        )
        return

    if data == "startedit:image_delete_all":
        conn = connect()
        cur = conn.cursor()

        try:
            cur.execute("""
                DELETE FROM start_images
            """)
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cur.close()
            conn.close()

        await query.edit_message_text(
            "تم حذف جميع صور الستارت ✅",
            reply_markup=_main_keyboard()
        )


async def _add_access(update):
    value = update.message.text.strip()

    conn = connect()
    cur = conn.cursor()

    try:
        if value.startswith("@"):
            username = value[1:].strip().lower()

            if not username:
                await update.message.reply_text(
                    "اليوزر غير صحيح."
                )
                return

            cur.execute("""
                INSERT INTO start_access
                (
                    username
                )
                VALUES (?)
            """, (username,))

        else:
            try:
                user_id = int(value)
            except ValueError:
                await update.message.reply_text(
                    "ارسل أيدي صحيح أو يوزر يبدأ بـ @."
                )
                return

            cur.execute("""
                INSERT INTO start_access
                (
                    user_id
                )
                VALUES (?)
            """, (user_id,))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تمت الإضافة إلى المسموحين بالوصول ✅"
    )


async def _delete_access(update):
    value = update.message.text.strip()

    conn = connect()
    cur = conn.cursor()

    try:
        if value.startswith("@"):
            username = value[1:].strip().lower()

            cur.execute("""
                DELETE FROM start_access
                WHERE username = ?
            """, (username,))

        else:
            try:
                user_id = int(value)
            except ValueError:
                await update.message.reply_text(
                    "ارسل أيدي صحيح أو يوزر يبدأ بـ @."
                )
                return

            cur.execute("""
                DELETE FROM start_access
                WHERE user_id = ?
            """, (user_id,))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    sessions.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "تم حذف الشخص من المسموحين ✅"
    )
