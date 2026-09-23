# handlers/banned_words.py

import re
from html import escape
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank_level

from handlers.moderation import (
    get_warning_count,
    add_warning,
    clear_warnings,
    parse_duration_token,
    save_mute,
    save_restriction,
    save_ban,
    mention_user,
)


# =========================================================
# الثوابت
# =========================================================

MIN_LEVEL = 4  # نائب المالك وفوق

PUNISHMENTS = {
    "انذار",
    "كتم",
    "تقييد",
    "حظر",
}

LIST_NAMES = {
    1: "الكلمات المحظورة",
    2: "الكلمات المحظورة 2",
}


# =========================================================
# قاعدة البيانات
# =========================================================

def create_banned_words_tables():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS banned_words (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                list_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                UNIQUE(chat_id, list_id, word)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS banned_words_settings (
                chat_id BIGINT NOT NULL,
                list_id INTEGER NOT NULL,

                enabled BOOLEAN NOT NULL DEFAULT FALSE,

                punishment TEXT NOT NULL DEFAULT 'انذار',
                punishment_duration INTEGER,

                warning_duration INTEGER,
                warning_punishment TEXT,
                warning_punishment_duration INTEGER,

                PRIMARY KEY(chat_id, list_id)
            )
        """)

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _ensure_settings(chat_id, list_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO banned_words_settings (
                chat_id,
                list_id
            )
            VALUES (%s, %s)
            ON CONFLICT (chat_id, list_id) DO NOTHING
        """, (chat_id, list_id))

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _get_settings(chat_id, list_id):
    _ensure_settings(chat_id, list_id)

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                enabled,
                punishment,
                punishment_duration,
                warning_duration,
                warning_punishment,
                warning_punishment_duration
            FROM banned_words_settings
            WHERE chat_id = %s
              AND list_id = %s
        """, (chat_id, list_id))

        row = cur.fetchone()

        if not row:
            return {
                "enabled": False,
                "punishment": "انذار",
                "punishment_duration": None,
                "warning_duration": None,
                "warning_punishment": None,
                "warning_punishment_duration": None,
            }

        return {
            "enabled": row[0],
            "punishment": row[1],
            "punishment_duration": row[2],
            "warning_duration": row[3],
            "warning_punishment": row[4],
            "warning_punishment_duration": row[5],
        }

    finally:
        cur.close()
        conn.close()


def _set_enabled(chat_id, list_id, enabled):
    _ensure_settings(chat_id, list_id)

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE banned_words_settings
            SET enabled = %s
            WHERE chat_id = %s
              AND list_id = %s
        """, (enabled, chat_id, list_id))

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _set_direct_punishment(
    chat_id,
    list_id,
    punishment,
    duration=None,
):
    _ensure_settings(chat_id, list_id)

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE banned_words_settings
            SET
                punishment = %s,
                punishment_duration = %s
            WHERE chat_id = %s
              AND list_id = %s
        """, (
            punishment,
            duration,
            chat_id,
            list_id,
        ))

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _set_warning_punishment(
    chat_id,
    list_id,
    warning_duration,
    punishment,
    punishment_duration,
):
    _ensure_settings(chat_id, list_id)

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE banned_words_settings
            SET
                punishment = 'انذار',
                warning_duration = %s,
                warning_punishment = %s,
                warning_punishment_duration = %s
            WHERE chat_id = %s
              AND list_id = %s
        """, (
            warning_duration,
            punishment,
            punishment_duration,
            chat_id,
            list_id,
        ))

        conn.commit()

    finally:
        cur.close()
        conn.close()


# =========================================================
# الكلمات
# =========================================================

def _get_words(chat_id, list_id):
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT word
            FROM banned_words
            WHERE chat_id = %s
              AND list_id = %s
            ORDER BY id ASC
        """, (chat_id, list_id))

        return [row[0] for row in cur.fetchall()]

    finally:
        cur.close()
        conn.close()


def _add_words(chat_id, list_id, words):
    if not words:
        return

    conn = connect()
    cur = conn.cursor()

    try:
        for word in words:
            cur.execute("""
                INSERT INTO banned_words (
                    chat_id,
                    list_id,
                    word
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, list_id, word) DO NOTHING
            """, (
                chat_id,
                list_id,
                word,
            ))

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _delete_words(chat_id, list_id, words):
    if not words:
        return

    conn = connect()
    cur = conn.cursor()

    try:
        for word in words:
            cur.execute("""
                DELETE FROM banned_words
                WHERE chat_id = %s
                  AND list_id = %s
                  AND word = %s
            """, (
                chat_id,
                list_id,
                word,
            ))

        conn.commit()

    finally:
        cur.close()
        conn.close()


# =========================================================
# الصلاحيات
# =========================================================

def _allowed(user_id):
    try:
        return get_rank_level(user_id) >= MIN_LEVEL
    except Exception:
        return False


async def _permission_denied(update):
    message = update.effective_message

    if message:
        await message.reply_text(
            "• هذا الأمر لـ نائب المالك وفوق فقط ."
        )


async def _callback_permission_denied(query):
    await query.answer(
        "• هذا الأمر لـ نائب المالك وفوق فقط .",
        show_alert=True,
    )


# =========================================================
# المنشن
# =========================================================

def _user_mention(user):
    try:
        return mention_user(user)
    except Exception:
        name = escape(user.full_name or "المشرف")
        return f'<a href="tg://user?id={user.id}">{name}</a>'


# =========================================================
# واجهة القائمة
# =========================================================

def _list_keyboard(list_id, enabled):
    state_text = (
        "اضغط لتعطيل الكلمات 🚫 ."
        if enabled
        else
        "اضغط لتفعيل الكلمات ✅ ."
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "اضافة كلمات ➕",
                callback_data=f"banned_words:add:{list_id}",
            ),
            InlineKeyboardButton(
                "حذف كلمات 🗑️",
                callback_data=f"banned_words:delete:{list_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                state_text,
                callback_data=f"banned_words:toggle:{list_id}",
            ),
        ],
    ])


def _back_close_keyboard(list_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "↩️ رجوع لقائمة الكلمات",
                callback_data=f"banned_words:list:{list_id}",
            ),
            InlineKeyboardButton(
                "اغلاق القائمة",
                callback_data="banned_words:close",
            ),
        ]
    ])


def _build_list_text(chat_id, list_id):
    words = _get_words(chat_id, list_id)
    settings = _get_settings(chat_id, list_id)

    if list_id == 1:
        title = "🚫 قائمة الكلمات المحظورة:"
    else:
        title = "🚫 قائمة الكلمات المحظورة 2:"

    lines = [title, ""]

    if words:
        for index, word in enumerate(words, 1):
            lines.append(f"{index} - {word}")
    else:
        lines.append("لا توجد كلمات محظورة حاليًا .")

    return "\n".join(lines), settings["enabled"]


async def _show_list_message(
    message,
    chat_id,
    list_id,
):
    text, enabled = _build_list_text(chat_id, list_id)

    await message.edit_text(
        text=text,
        reply_markup=_list_keyboard(list_id, enabled),
    )


async def _send_list_message(
    context,
    chat_id,
    list_id,
):
    text, enabled = _build_list_text(chat_id, list_id)

    return await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=_list_keyboard(list_id, enabled),
    )


# =========================================================
# أمر فتح القائمة
# =========================================================

async def banned_words_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    text = (message.text or "").strip()

    if text not in (
        "الكلمات المحظورة",
        "الكلمات المحظورة2",
    ):
        return

    if not _allowed(user.id):
        await _permission_denied(update)
        return

    list_id = 1 if text == "الكلمات المحظورة" else 2

    mention = _user_mention(user)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "هنا 👆🏻",
                callback_data=f"banned_words:list:{list_id}",
            ),
            InlineKeyboardButton(
                "فتح القائمة بالخاص❕",
                callback_data=f"banned_words:private:{list_id}",
            ),
        ]
    ])

    await message.reply_text(
        f"اهلًا يالمشرف {mention}",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# =========================================================
# قراءة الكلمات من الرسالة
# =========================================================

def _clean_words(text):
    result = []

    for line in text.splitlines():
        word = line.strip()

        if not word:
            continue

        if word not in result:
            result.append(word)

    return result


# =========================================================
# استقبال الإضافة / الحذف
# =========================================================

async def _finish_word_input(
    update,
    context,
    mode,
    list_id,
):
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return False

    if not _allowed(user.id):
        await _permission_denied(update)

        context.user_data.pop("banned_words_session", None)
        return True

    words = _clean_words(message.text or "")

    if not words:
        return True

    session = context.user_data.get("banned_words_session")

    if not session:
        return False

    prompt_chat_id = session.get("prompt_chat_id")
    prompt_message_id = session.get("prompt_message_id")

    if mode == "add":
        _add_words(
            session["chat_id"],
            list_id,
            words,
        )

        success = "تم حفظ الكلمات بنجاح ✅ ."

    else:
        _delete_words(
            session["chat_id"],
            list_id,
            words,
        )

        success = "تم حذف الكلمات بنجاح ✅ ."

    if prompt_chat_id and prompt_message_id:
        try:
            await context.bot.delete_message(
                chat_id=prompt_chat_id,
                message_id=prompt_message_id,
            )
        except Exception:
            pass

    sent = await message.reply_text(
        success,
        reply_markup=_back_close_keyboard(list_id),
    )

    context.user_data.pop("banned_words_session", None)

    return True


# =========================================================
# استقبال إعداد العقوبات
# =========================================================

_DURATION_RE = re.compile(
    r"^\s*(\d+)\s*(ث|ثانية|ثواني|د|دقيقة|دقائق|س|ساعة|ساعات|ي|يوم|أيام)\s*$"
)


def _parse_duration(text):
    text = text.strip()

    if not _DURATION_RE.match(text):
        return None

    try:
        return parse_duration_token(text)
    except Exception:
        return None


def _parse_warning_config(text):
    parts = text.split()

    if len(parts) < 2:
        return None

    warning_duration = _parse_duration(parts[0])

    if warning_duration is None:
        return None

    punishment = parts[1].strip()

    if punishment not in ("كتم", "تقييد", "حظر"):
        return None

    punishment_duration = None

    if punishment != "حظر":
        if len(parts) < 3:
            return None

        punishment_duration = _parse_duration(parts[2])

        if punishment_duration is None:
            return None

    return (
        warning_duration,
        punishment,
        punishment_duration,
    )


async def _finish_punishment_input(
    update,
    context,
):
    message = update.effective_message
    user = update.effective_user

    session = context.user_data.get(
        "banned_words_punishment_session"
    )

    if not session:
        return False

    if not _allowed(user.id):
        await _permission_denied(update)
        context.user_data.pop(
            "banned_words_punishment_session",
            None,
        )
        return True

    chat_id = session["chat_id"]
    list_id = session["list_id"]
    punishment = session["punishment"]

    text = (message.text or "").strip()

    if punishment == "انذار":
        parsed = _parse_warning_config(text)

        if not parsed:
            await message.reply_text(
                "• الصيغة غير صحيحة .\n\n"
                "مثال:\n\n"
                "3د كتم 5ي"
            )
            return True

        warning_duration, next_punishment, punishment_duration = parsed

        _set_warning_punishment(
            chat_id,
            list_id,
            warning_duration,
            next_punishment,
            punishment_duration,
        )

        await message.reply_text(
            "تم حفظ عقوبة الإنذارات بنجاح ✅ ."
        )

    else:
        duration = _parse_duration(text)

        if duration is None:
            await message.reply_text(
                "• أرسل المدة بهذا الشكل:\n\n"
                "5ي\n"
                "30ث\n"
                "50د\n"
                "1س"
            )
            return True

        _set_direct_punishment(
            chat_id,
            list_id,
            punishment,
            duration,
        )

        await message.reply_text(
            "تم حفظ العقوبة بنجاح ✅ ."
        )

    context.user_data.pop(
        "banned_words_punishment_session",
        None,
    )

    return True


# =========================================================
# معالج رسائل الإعداد
# =========================================================

async def banned_words_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    text = (message.text or "").strip()

    # -----------------------------------------
    # إدخال كلمات
    # -----------------------------------------

    word_session = context.user_data.get(
        "banned_words_session"
    )

    if word_session:
        return await _finish_word_input(
            update,
            context,
            word_session["mode"],
            word_session["list_id"],
        )

    # -----------------------------------------
    # إعداد عقوبة
    # -----------------------------------------

    punishment_session = context.user_data.get(
        "banned_words_punishment_session"
    )

    if punishment_session:
        return await _finish_punishment_input(
            update,
            context,
        )

    # -----------------------------------------
    # ضع عقوبة القائمة الأولى
    # -----------------------------------------

    patterns = [
        (
            r"^ضع عقوبة الكلمات المحظورة/ه (انذار|كتم|تقييد|حظر)$",
            1,
        ),
        (
            r"^ضع عقوبة الكلمات المحظورة/ه2 (انذار|كتم|تقييد|حظر)$",
            2,
        ),
    ]

    for pattern, list_id in patterns:
        match = re.match(pattern, text)

        if not match:
            continue

        if not _allowed(user.id):
            await _permission_denied(update)
            return

        punishment = match.group(1)

        if punishment == "انذار":
            await message.reply_text(
                "• تمام، أرسل مدة الانذار+ العقوبة الي بعد الانذارات "
                "مع المدة بهذي الطريقة:\n\n"
                "3د كتم 5ي"
            )

        elif punishment == "حظر":
            _set_direct_punishment(
                message.chat_id,
                list_id,
                "حظر",
                None,
            )

            await message.reply_text(
                "تم حفظ العقوبة بنجاح ✅ ."
            )
            return

        else:
            names = {
                "كتم": "الكتم",
                "تقييد": "التقييد",
            }

            await message.reply_text(
                f"• حسنًا اختر مدة {names[punishment]} ."
            )

        context.user_data["banned_words_punishment_session"] = {
            "chat_id": message.chat_id,
            "list_id": list_id,
            "punishment": punishment,
        }

        return

    # -----------------------------------------
    # التفعيل والتعطيل
    # -----------------------------------------

    toggle_patterns = {
        "تفعيل الكلمات المحظورة/ه": (1, True),
        "تعطيل الكلمات المحظورة": (1, False),

        "تفعيل الكلمات المحظورة/ه2": (2, True),
        "تعطيل الكلمات المحظورة2": (2, False),
    }

    if text in toggle_patterns:
        list_id, enabled = toggle_patterns[text]

        if not _allowed(user.id):
            await _permission_denied(update)
            return

        _set_enabled(
            message.chat_id,
            list_id,
            enabled,
        )

        if enabled:
            await message.reply_text(
                "تم تفعيل الكلمات المحظورة ✅ ."
            )
        else:
            await message.reply_text(
                "تم تعطيل الكلمات المحظورة 🚫 ."
            )

        return


# =========================================================
# أزرار القائمة
# =========================================================

async def banned_words_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = query.from_user

    if not _allowed(user.id):
        await _callback_permission_denied(query)
        return

    data = query.data or ""

    if not data.startswith("banned_words:"):
        return

    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    # =====================================================
    # إغلاق
    # =====================================================

    if action == "close":
        try:
            await query.message.delete()
        except Exception:
            pass

        return

    # =====================================================
    # فتح القائمة
    # =====================================================

    if action == "list":
        if len(parts) < 3:
            return

        list_id = int(parts[2])

        await _show_list_message(
            query.message,
            query.message.chat_id,
            list_id,
        )

        return

    # =====================================================
    # فتح القائمة بالخاص
    # =====================================================

    if action == "private":
        if len(parts) < 3:
            return

        list_id = int(parts[2])

        await query.edit_message_text(
            "تم الإرسال بالخاص ✅ ."
        )

        await _send_list_message(
            context,
            user.id,
            list_id,
        )

        return

    # =====================================================
    # إضافة
    # =====================================================

    if action == "add":
        if len(parts) < 3:
            return

        list_id = int(parts[2])

        prompt = await query.edit_message_text(
            "• حسنًا ارسل الكلمات التي تريد إضافتها .\n\n"
            "مثال:\n\n"
            "كلزق\n"
            "كلتبن\n"
            "ياكلب\n"
            "الخ…"
        )

        context.user_data["banned_words_session"] = {
            "mode": "add",
            "list_id": list_id,
            "chat_id": query.message.chat_id,
            "prompt_chat_id": query.message.chat_id,
            "prompt_message_id": prompt.message_id,
        }

        return

    # =====================================================
    # حذف
    # =====================================================

    if action == "delete":
        if len(parts) < 3:
            return

        list_id = int(parts[2])

        prompt = await query.edit_message_text(
            "• حسنًا ارسل الكلمات التي تريد حذفها .\n\n"
            "مثال:\n\n"
            "كلزق\n"
            "كلتبن\n"
            "ياكلب\n"
            "الخ…"
        )

        context.user_data["banned_words_session"] = {
            "mode": "delete",
            "list_id": list_id,
            "chat_id": query.message.chat_id,
            "prompt_chat_id": query.message.chat_id,
            "prompt_message_id": prompt.message_id,
        }

        return

    # =====================================================
    # تفعيل / تعطيل
    # =====================================================

    if action == "toggle":
        if len(parts) < 3:
            return

        list_id = int(parts[2])

        settings = _get_settings(
            query.message.chat_id,
            list_id,
        )

        new_state = not settings["enabled"]

        _set_enabled(
            query.message.chat_id,
            list_id,
            new_state,
        )

        await _show_list_message(
            query.message,
            query.message.chat_id,
            list_id,
        )

        return


# =========================================================
# مطابقة الكلمات
# =========================================================

_ARABIC_LETTER_OR_NUMBER = (
    "ء-ي"
    "A-Za-z"
    "0-9"
    "_"
)


def _word_exists(text, word):
    if not word:
        return False

    pattern = (
        rf"(?<![{_ARABIC_LETTER_OR_NUMBER}])"
        rf"{re.escape(word)}"
        rf"(?![{_ARABIC_LETTER_OR_NUMBER}])"
    )

    return re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    ) is not None


def _find_banned_word(text, words):
    for word in words:
        if _word_exists(text, word):
            return word

    return None


# =========================================================
# العقوبات
# =========================================================

async def _apply_mute(
    context,
    chat_id,
    user,
    duration,
):
    if duration is None:
        return

    until_timestamp = int(datetime.now(
        timezone.utc
    ).timestamp()) + int(duration)

    until_date = datetime.fromtimestamp(
        until_timestamp,
        tz=timezone.utc,
    )

    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user.id,
        permissions=ChatPermissions(
            can_send_messages=False,
        ),
        until_date=until_date,
    )

    try:
        save_mute(
            chat_id,
            user.id,
            until_timestamp,
        )
    except Exception:
        pass


async def _apply_restrict(
    context,
    chat_id,
    user,
    duration,
):
    if duration is None:
        return

    until_timestamp = int(datetime.now(
        timezone.utc
    ).timestamp()) + int(duration)

    until_date = datetime.fromtimestamp(
        until_timestamp,
        tz=timezone.utc,
    )

    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user.id,
        permissions=ChatPermissions(
            can_send_messages=False,
        ),
        until_date=until_date,
    )

    try:
        save_restriction(
            chat_id,
            user.id,
            until_timestamp,
        )
    except Exception:
        pass


async def _apply_ban(
    context,
    chat_id,
    user,
):
    await context.bot.ban_chat_member(
        chat_id=chat_id,
        user_id=user.id,
    )

    try:
        save_ban(
            chat_id,
            user.id,
        )
    except Exception:
        pass


async def _apply_punishment(
    update,
    context,
    punishment,
    duration,
):
    message = update.effective_message
    user = update.effective_user

    if punishment == "كتم":
        await _apply_mute(
            context,
            message.chat_id,
            user,
            duration,
        )

    elif punishment == "تقييد":
        await _apply_restrict(
            context,
            message.chat_id,
            user,
            duration,
        )

    elif punishment == "حظر":
        await _apply_ban(
            context,
            message.chat_id,
            user,
        )


# =========================================================
# نظام الإنذار المشترك
# =========================================================

async def _handle_warning_punishment(
    update,
    context,
    list_id,
):
    message = update.effective_message
    user = update.effective_user

    chat_id = message.chat_id

    # نفس warnings الموجود في moderation.py
    add_warning(
        chat_id,
        user.id,
        source="banned_words",
    )

    count = get_warning_count(
        chat_id,
        user.id,
    )

    user_mention = _user_mention(user)

    await message.reply_text(
        "• كتب كلمة محظورة وجاه انذار .\n"
        f"• المستخدم ↤︎ {user_mention}\n"
        f"• عدد إنذاراته ↤︎ {count}",
        parse_mode="HTML",
    )

    # الوصول إلى 3 إنذارات
    if count < 3:
        return

    settings = _get_settings(
        chat_id,
        list_id,
    )

    punishment = settings["warning_punishment"]
    punishment_duration = settings[
        "warning_punishment_duration"
    ]

    if punishment not in (
        "كتم",
        "تقييد",
        "حظر",
    ):
        return

    if punishment == "حظر":
        await _apply_ban(
            context,
            chat_id,
            user,
        )

        await message.reply_text(
            "• تجاوز الإنذارات وتم حظره .\n"
            f"• المستخدم ↤︎ {user_mention}",
            parse_mode="HTML",
        )

    elif punishment == "كتم":
        await _apply_mute(
            context,
            chat_id,
            user,
            punishment_duration,
        )

        await message.reply_text(
            "• تجاوز الإنذارات وتم كتمه .\n"
            f"• المستخدم ↤︎ {user_mention}",
            parse_mode="HTML",
        )

    elif punishment == "تقييد":
        await _apply_restrict(
            context,
            chat_id,
            user,
            punishment_duration,
        )

        await message.reply_text(
            "• تجاوز الإنذارات وتم تقييده .\n"
            f"• المستخدم ↤︎ {user_mention}",
            parse_mode="HTML",
        )

    # مهم:
    # بعد تطبيق العقوبة يتم تصفير نفس warnings المشترك.
    clear_warnings(
        chat_id,
        user.id,
    )


# =========================================================
# مراقبة الكلمات المحظورة
# =========================================================

async def banned_words_enforcement_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    if not message.chat:
        return

    if message.chat.type not in (
        "group",
        "supergroup",
    ):
        return

    text = message.text or message.caption or ""

    if not text:
        return

    chat_id = message.chat_id

    # -----------------------------------------------------
    # القائمة الأولى والثانية مستقلتان
    # -----------------------------------------------------

    for list_id in (1, 2):

        settings = _get_settings(
            chat_id,
            list_id,
        )

        if not settings["enabled"]:
            continue

        words = _get_words(
            chat_id,
            list_id,
        )

        if not words:
            continue

        matched = _find_banned_word(
            text,
            words,
        )

        if not matched:
            continue

        punishment = settings["punishment"]

        # -------------------------------------------------
        # إنذار
        # -------------------------------------------------

        if punishment == "انذار":
            await _handle_warning_punishment(
                update,
                context,
                list_id,
            )

        # -------------------------------------------------
        # كتم
        # -------------------------------------------------

        elif punishment == "كتم":
            duration = settings[
                "punishment_duration"
            ]

            await _apply_mute(
                context,
                chat_id,
                user,
                duration,
            )

        # -------------------------------------------------
        # تقييد
        # -------------------------------------------------

        elif punishment == "تقييد":
            duration = settings[
                "punishment_duration"
            ]

            await _apply_restrict(
                context,
                chat_id,
                user,
                duration,
            )

        # -------------------------------------------------
        # حظر
        # -------------------------------------------------

        elif punishment == "حظر":
            await _apply_ban(
                context,
                chat_id,
                user,
            )

        # لا نطبق القائمتين على نفس الرسالة.
        break
