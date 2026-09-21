# =========================================================
# handlers/repetition.py
# نظام حماية التكرار
# متوافق مع python-telegram-bot 22.8
# =========================================================

import asyncio
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

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

from handlers.roles import (
    get_rank_level,
    get_rank,
    is_primary_developer,
)

from handlers.moderation import (
    parse_duration_token,
    format_duration,
    save_mute,
    save_restriction,
    save_ban,
    mention_user,
)

OWNER_ID = 8453977662

# =========================================================
# ذاكرة الرسائل الأخيرة
#
# chat_id
#   └── user_id
#        └── deque(message_id, timestamp)
# =========================================================

_repetition_messages = defaultdict(
    lambda: defaultdict(deque)
)

_repetition_locks = defaultdict(asyncio.Lock)


# =========================================================
# جلسات الإعداد
# =========================================================

repetition_sessions = {}


# =========================================================
# أسماء العقوبات
# =========================================================

ACTION_NAMES = {
    "كتم": "mute",
    "تقييد": "restrict",
    "حظر": "ban",
}

ACTION_DISPLAY = {
    "mute": "كتم",
    "restrict": "تقييد",
    "ban": "حظر",
}


# =========================================================
# أدوات الوقت
# =========================================================

def now():
    return datetime.now()


# =========================================================
# جلب إعدادات التكرار
# =========================================================

def get_repetition_settings_sync(chat_id):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                repetition_enabled,
                repetition_limit,
                repetition_seconds,
                repetition_action,
                repetition_warning_duration,
                repetition_punishment_duration,
                repetition_rank
            FROM protection_settings
            WHERE chat_id=?
            LIMIT 1
        """, (chat_id,))

        row = cur.fetchone()

        if not row:

            cur.execute("""
                INSERT INTO protection_settings (
                    chat_id,
                    repetition_enabled,
                    repetition_limit,
                    repetition_seconds,
                    repetition_action,
                    repetition_warning_duration,
                    repetition_punishment_duration,
                    repetition_rank
                )
                VALUES (?, 0, 3, 5, 'mute', 3600, 300, 'عضو')
                ON CONFLICT(chat_id)
                DO NOTHING
            """, (chat_id,))

            conn.commit()

            return {
                "enabled": False,
                "limit": 3,
                "seconds": 5,
                "action": "mute",
                "warning_duration": 3600,
                "punishment_duration": 300,
                "rank": "عضو",
            }

        return {
            "enabled": bool(row[0]),
            "limit": int(row[1] or 3),
            "seconds": int(row[2] or 5),
            "action": row[3] or "mute",
            "warning_duration": int(row[4] or 3600),
            "punishment_duration": int(row[5] or 300),
            "rank": row[6] or "عضو",
        }

    finally:

        cur.close()
        conn.close()


async def get_repetition_settings(chat_id):

    return await asyncio.to_thread(
        get_repetition_settings_sync,
        chat_id
    )


# =========================================================
# حفظ إعداد
# =========================================================

def update_repetition_setting(
    chat_id,
    field,
    value
):

    allowed = {
        "repetition_enabled",
        "repetition_limit",
        "repetition_seconds",
        "repetition_action",
        "repetition_warning_duration",
        "repetition_punishment_duration",
        "repetition_rank",
    }

    if field not in allowed:
        raise ValueError("Invalid repetition setting")

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO protection_settings (chat_id)
            VALUES (?)
            ON CONFLICT(chat_id)
            DO NOTHING
        """, (chat_id,))

        cur.execute(
            f"""
            UPDATE protection_settings
            SET {field}=?
            WHERE chat_id=?
            """,
            (value, chat_id)
        )

        conn.commit()

    finally:

        cur.close()
        conn.close()


async def set_repetition_setting(
    chat_id,
    field,
    value
):

    await asyncio.to_thread(
        update_repetition_setting,
        chat_id,
        field,
        value
    )


# =========================================================
# الرتبة المستهدفة
# =========================================================

def repetition_rank_allowed(
    user_id,
    target_rank
):

    # المطور الأساسي مستثنى دائمًا
    if is_primary_developer(user_id):
        return False

    level = get_rank_level(user_id)

    if target_rank == "عضو":
        return level == 0

    if target_rank == "مميز":
        return level <= 1

    if target_rank == "ادمن":
        return level <= 2

    if target_rank == "ادمن اساسي":
        return level <= 3

    if target_rank == "نائب المالك":
        return level <= 4

    if target_rank == "المالك":
        return level <= 5

    if target_rank == "Dev":
        return level <= 6

    return level == 0


# =========================================================
# تنظيف رسائل المستخدم القديمة من الذاكرة
# =========================================================

def cleanup_user_messages(
    chat_id,
    user_id,
    window_seconds
):

    messages = _repetition_messages[
        chat_id
    ][
        user_id
    ]

    cutoff = now() - timedelta(
        seconds=window_seconds
    )

    while messages and messages[0][1] < cutoff:

        messages.popleft()


# =========================================================
# تسجيل الرسالة
# =========================================================

async def register_repetition_message(
    update,
    context
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return False

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return False

    settings = await get_repetition_settings(
        chat.id
    )

    if not settings["enabled"]:
        return False

    if not repetition_rank_allowed(
        user.id,
        settings["rank"]
    ):
        return False

    # =====================================================
    # لا نحسب أوامر البوت؟
    #
    # حسب المطلوب: أي رسالة من المستخدم تحسب.
    # =====================================================

    key = (
        chat.id,
        user.id
    )

    async with _repetition_locks[key]:

        messages = _repetition_messages[
            chat.id
        ][
            user.id
        ]

        cleanup_user_messages(
            chat.id,
            user.id,
            settings["seconds"]
        )

        messages.append((
            message.message_id,
            now()
        ))

        # نحتاج آخر N فقط على الأقل
        while len(messages) > settings["limit"]:

            messages.popleft()

        if len(messages) < settings["limit"]:
            return False

        # =================================================
        # تحقق من أن N رسالة فعلًا داخل المدة
        # =================================================

        first_time = messages[0][1]
        elapsed = (
            now() - first_time
        ).total_seconds()

        if elapsed > settings["seconds"]:

            cleanup_user_messages(
                chat.id,
                user.id,
                settings["seconds"]
            )

            return False

        # =================================================
        # حصل التكرار
        # =================================================

        message_ids = [
            item[0]
            for item in messages
        ]

        await handle_repetition_trigger(
            update,
            context,
            settings,
            message_ids
        )

        # بعد العقوبة/الإنذار نبدأ نافذة جديدة
        messages.clear()

        return True


# =========================================================
# حذف آخر N رسائل
# =========================================================

async def delete_repetition_messages(
    context,
    chat_id,
    message_ids
):

    for message_id in message_ids:

        try:

            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception:
            pass


# =========================================================
# عدد الإنذارات النشطة
# =========================================================

def get_warning_count_sync(
    chat_id,
    user_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM repetition_warnings
            WHERE expires_at <= CURRENT_TIMESTAMP
        """)

        conn.commit()

        cur.execute("""
            SELECT COUNT(*)
            FROM repetition_warnings
            WHERE chat_id=?
            AND user_id=?
        """, (
            chat_id,
            user_id
        ))

        row = cur.fetchone()

        return int(row[0] or 0)

    finally:

        cur.close()
        conn.close()


async def get_warning_count(
    chat_id,
    user_id
):

    return await asyncio.to_thread(
        get_warning_count_sync,
        chat_id,
        user_id
    )


# =========================================================
# إضافة إنذار
# =========================================================

def add_warning_sync(
    chat_id,
    user_id,
    duration
):

    conn = connect()
    cur = conn.cursor()

    try:

        expires = now() + timedelta(
            seconds=duration
        )

        cur.execute("""
            INSERT INTO repetition_warnings (
                chat_id,
                user_id,
                expires_at
            )
            VALUES (?, ?, ?)
        """, (
            chat_id,
            user_id,
            expires
        ))

        conn.commit()

        cur.execute("""
            SELECT COUNT(*)
            FROM repetition_warnings
            WHERE chat_id=?
            AND user_id=?
            AND expires_at > CURRENT_TIMESTAMP
        """, (
            chat_id,
            user_id
        ))

        row = cur.fetchone()

        return int(row[0] or 0)

    finally:

        cur.close()
        conn.close()


async def add_warning(
    chat_id,
    user_id,
    duration
):

    return await asyncio.to_thread(
        add_warning_sync,
        chat_id,
        user_id,
        duration
    )


# =========================================================
# مسح الإنذارات
# =========================================================

def clear_warnings_sync(
    chat_id,
    user_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM repetition_warnings
            WHERE chat_id=?
            AND user_id=?
        """, (
            chat_id,
            user_id
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()


async def clear_warnings(
    chat_id,
    user_id
):

    await asyncio.to_thread(
        clear_warnings_sync,
        chat_id,
        user_id
    )


# =========================================================
# رسالة التحذير
# =========================================================

async def send_repetition_warning(
    update,
    warning_number
):

    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    await message.reply_text(
        (
            f"• تحذير التكرار رقم {warning_number}\n\n"
            f"المستخدم ↤︎ "
            f"{mention_user(user)}"
        ),
        parse_mode="HTML"
    )


# =========================================================
# تنفيذ العقوبة
# =========================================================

async def punish_repetition(
    update,
    context,
    settings
):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    action = settings["action"]
    duration = settings["punishment_duration"]

    # =====================================================
    # كتم
    # =====================================================

    if action == "mute":

        await save_mute(
            chat_id=chat.id,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            until_time=(
                now() +
                timedelta(seconds=duration)
            ),
            reason="التكرار",
            by_user=OWNER_ID
        )

        punishment_text = (
            f"كتم لمدة {format_duration(duration)}"
        )

    # =====================================================
    # تقييد
    # =====================================================

    elif action == "restrict":

        until_date = (
            now() +
            timedelta(seconds=duration)
        )

        permissions = ChatPermissions(
            can_send_messages=False
        )

        try:

            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=permissions,
                until_date=until_date
            )

        except Exception:
            pass

        await save_restriction(
            chat_id=chat.id,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            until_time=until_date,
            reason="التكرار",
            by_user=OWNER_ID
        )

        punishment_text = (
            f"تقييد لمدة {format_duration(duration)}"
        )

    # =====================================================
    # حظر
    # =====================================================

    elif action == "ban":

        try:

            await context.bot.ban_chat_member(
                chat_id=chat.id,
                user_id=user.id
            )

        except Exception:
            pass

        await save_ban(
            chat_id=chat.id,
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            reason="التكرار",
            by_user=OWNER_ID
        )

        punishment_text = "حظر"

    else:
        return

    await clear_warnings(
        chat.id,
        user.id
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            "• تم "
            f"{ACTION_DISPLAY.get(action, action)}ك "
            "بسبب التكرار\n"
            f"العقوبة: {punishment_text}\n\n"
            f"المستخدم ↤︎ {mention_user(user)}"
        ),
        parse_mode="HTML"
    )


# =========================================================
# عند حصول التكرار
# =========================================================

async def handle_repetition_trigger(
    update,
    context,
    settings,
    message_ids
):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    # =====================================================
    # نحذف آخر N رسائل فقط
    # =====================================================

    await delete_repetition_messages(
        context,
        chat.id,
        message_ids[-settings["limit"]:]
    )

    # =====================================================
    # عدد الإنذارات الحالية قبل إضافة الجديد
    # =====================================================

    current = await get_warning_count(
        chat.id,
        user.id
    )

    # =====================================================
    # الإنذار الثالث = عقوبة مباشرة
    # =====================================================

    if current >= 2:

        await punish_repetition(
            update,
            context,
            settings
        )

        return

    # =====================================================
    # إضافة إنذار جديد
    # =====================================================

    warning_number = await add_warning(
        chat.id,
        user.id,
        settings["warning_duration"]
    )

    if warning_number >= 3:

        await punish_repetition(
            update,
            context,
            settings
        )

        return

    await send_repetition_warning(
        update,
        warning_number
    )


# =========================================================
# أمر التكرار الرئيسي
# =========================================================

async def repetition_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    # =====================================================
    # الأوامر الإدارية
    # =====================================================

    text = (
        message.text or ""
    ).strip()

    normalized = re.sub(
        r"\s+",
        " ",
        text
    )

    # =====================================================
    # تفعيل
    # =====================================================

    if normalized in (
        "تفعيل التكرار",
    ):

        if get_rank_level(user.id) < 2:
            return

        await set_repetition_setting(
            chat.id,
            "repetition_enabled",
            1
        )

        await message.reply_text(
            "• تم تفعيل حماية التكرار بنجاح ."
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تعطيل
    # =====================================================

    if normalized in (
        "تعطيل التكرار",
    ):

        if get_rank_level(user.id) < 2:
            return

        await set_repetition_setting(
            chat.id,
            "repetition_enabled",
            0
        )

        await message.reply_text(
            "• تم تعطيل حماية التكرار بنجاح ."
        )

        raise ApplicationHandlerStop

    # =====================================================
    # ضع تكرار 5
    # =====================================================

    match = re.fullmatch(
        r"ضع\s+تكرار\s+(\d+)",
        normalized
    )

    if match:

        if get_rank_level(user.id) < 2:
            return

        limit = int(
            match.group(1)
        )

        if limit < 1:
            return

        repetition_sessions[user.id] = {
            "chat_id": chat.id,
            "action": "repetition_duration",
            "limit": limit
        }

        await message.reply_text(
            "حسنًا، ارسل المدة التي تريدها ."
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تعيين مدة انذار
    # =====================================================

    match = re.fullmatch(
        r"تعيين\s+مدة\s+انذار\s+(.+)",
        normalized
    )

    if match:

        if get_rank_level(user.id) < 2:
            return

        duration = parse_duration_token(
            match.group(1).strip()
        )

        if not duration:
            return

        await set_repetition_setting(
            chat.id,
            "repetition_warning_duration",
            duration
        )

        await message.reply_text(
            "• تم تعيين مدة الإنذار بنجاح ."
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تغيير عقوبة التكرار
    # =====================================================

    if normalized == "تغيير عقوبة التكرار":

        if get_rank_level(user.id) < 2:
            return

        repetition_sessions[user.id] = {
            "chat_id": chat.id,
            "action": "repetition_action"
        }

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "كتم",
                    callback_data="repetition:action:mute"
                ),
                InlineKeyboardButton(
                    "تقييد",
                    callback_data="repetition:action:restrict"
                ),
                InlineKeyboardButton(
                    "حظر",
                    callback_data="repetition:action:ban"
                )
            ]
        ])

        await message.reply_text(
            "حسنًا، ارسل العقوبة الجديدة .",
            reply_markup=keyboard
        )

        raise ApplicationHandlerStop

    # =====================================================
    # مدة كتم التكرار
    # =====================================================

    match = re.fullmatch(
        r"ضع\s+كتم\s+تكرار\s+(.+)",
        normalized
    )

    if match:

        if get_rank_level(user.id) < 2:
            return

        duration = parse_duration_token(
            match.group(1).strip()
        )

        if not duration:
            return

        settings = await get_repetition_settings(
            chat.id
        )

        if settings["action"] != "mute":

            await message.reply_text(
                "• العقوبة الحالية هي "
                f"{ACTION_DISPLAY.get(settings['action'], settings['action'])}، "
                "لذلك استخدم إعداد مدة العقوبة الحالية."
            )

            raise ApplicationHandlerStop

        await set_repetition_setting(
            chat.id,
            "repetition_punishment_duration",
            duration
        )

        await message.reply_text(
            "• تم تعيين مدة الكتم للتكرار بنجاح ."
        )

        raise ApplicationHandlerStop

    # =====================================================
    # مدة تقييد التكرار
    # =====================================================

    match = re.fullmatch(
        r"ضع\s+تقييد\s+تكرار\s+(.+)",
        normalized
    )

    if match:

        if get_rank_level(user.id) < 2:
            return

        duration = parse_duration_token(
            match.group(1).strip()
        )

        if not duration:
            return

        settings = await get_repetition_settings(
            chat.id
        )

        if settings["action"] != "restrict":

            await message.reply_text(
                "• العقوبة الحالية هي "
                f"{ACTION_DISPLAY.get(settings['action'], settings['action'])}، "
                "لذلك استخدم إعداد مدة العقوبة الحالية."
            )

            raise ApplicationHandlerStop

        await set_repetition_setting(
            chat.id,
            "repetition_punishment_duration",
            duration
        )

        await message.reply_text(
            "• تم تعيين مدة التقييد للتكرار بنجاح ."
        )

        raise ApplicationHandlerStop

    # =====================================================
    # رتبة التكرار
    # =====================================================

    match = re.fullmatch(
        r"ضع\s+رتبة\s+التكرار\s+(.+)",
        normalized
    )

    if match:

        if get_rank_level(user.id) < 3:
            return

        rank = match.group(1).strip()

        valid_ranks = (
            "عضو",
            "مميز",
            "ادمن",
            "ادمن اساسي",
            "نائب المالك",
            "المالك",
            "Dev",
        )

        if rank not in valid_ranks:
            return

        await set_repetition_setting(
            chat.id,
            "repetition_rank",
            rank
        )

        await message.reply_text(
            f"• تم تعيين رتبة التكرار على: {rank}"
        )

        raise ApplicationHandlerStop


# =========================================================
# استقبال جلسات إعداد التكرار
# =========================================================

async def repetition_session_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    session = repetition_sessions.get(
        user.id
    )

    if not session:
        return

    if session.get("chat_id") != chat.id:
        return

    text = (
        message.text or ""
    ).strip()

    action = session.get(
        "action"
    )

    # =====================================================
    # مدة التكرار
    # =====================================================

    if action == "repetition_duration":

        duration = parse_duration_token(
            text
        )

        if not duration:

            await message.reply_text(
                "• المدة غير صحيحة، مثال: 3ث أو 5د أو 1س."
            )

            raise ApplicationHandlerStop

        await set_repetition_setting(
            chat.id,
            "repetition_limit",
            session["limit"]
        )

        await set_repetition_setting(
            chat.id,
            "repetition_seconds",
            duration
        )

        repetition_sessions.pop(
            user.id,
            None
        )

        await message.reply_text(
            (
                "• تم حفظ إعداد التكرار بنجاح .\n\n"
                f"عدد الرسائل ↤︎ {session['limit']}\n"
                f"المدة ↤︎ {format_duration(duration)}"
            )
        )

        raise ApplicationHandlerStop

    raise ApplicationHandlerStop


# =========================================================
# أزرار تغيير العقوبة
# =========================================================

async def repetition_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    user = query.from_user

    if not user:
        return

    if not query.data.startswith(
        "repetition:action:"
    ):
        return

    await query.answer()

    if get_rank_level(user.id) < 2:
        return

    action = query.data.split(":")[-1]

    if action not in (
        "mute",
        "restrict",
        "ban"
    ):
        return

    chat_id = (
        query.message.chat.id
        if query.message
        else None
    )

    if not chat_id:
        return

    await set_repetition_setting(
        chat_id,
        "repetition_action",
        action
    )

    repetition_sessions.pop(
        user.id,
        None
    )

    await query.edit_message_text(
        (
            "• تم تغيير عقوبة التكرار بنجاح .\n"
            f"العقوبة ↤︎ {ACTION_DISPLAY[action]}"
        )
    )


# =========================================================
# مسح إنذارات شخص
# =========================================================

async def clear_repetition_warnings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if get_rank_level(user.id) < 2:
        return

    target = None

    if message.reply_to_message:

        target = message.reply_to_message.from_user

    else:

        parts = (
            message.text or ""
        ).split()

        if len(parts) >= 2:

            value = parts[1].strip()

            if value.isdigit():

                try:

                    target = await context.bot.get_chat(
                        int(value)
                    )

                except Exception:
                    target = None

            elif value.startswith("@"):

                try:

                    target = await context.bot.get_chat(
                        value
                    )

                except Exception:
                    target = None

    if not target:

        await message.reply_text(
            "• استخدم الأمر بالرد على الشخص أو ضع الـ ID."
        )

        raise ApplicationHandlerStop

    await clear_warnings(
        chat.id,
        target.id
    )

    await message.reply_text(
        (
            "• تم مسح إنذاراته بنجاح .\n"
            f"المستخدم ↤︎ {mention_user(target)}"
        ),
        parse_mode="HTML"
    )

    raise ApplicationHandlerStop


# =========================================================
# معالج الرسائل
# =========================================================

async def repetition_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # أولًا جلسات الإعداد
    if (
        update.effective_chat
        and update.effective_chat.type in (
            "group",
            "supergroup"
        )
        and update.effective_user
        and update.effective_user.id in repetition_sessions
    ):

        await repetition_session_message(
            update,
            context
        )

        return

    # ثم حماية التكرار
    await register_repetition_message(
        update,
        context
    )


# =========================================================
# حلقة تنظيف الإنذارات المنتهية
# =========================================================

async def repetition_expiry_loop(
    application
):

    while True:

        try:

            conn = connect()
            cur = conn.cursor()

            try:

                cur.execute("""
                    DELETE FROM repetition_warnings
                    WHERE expires_at <= CURRENT_TIMESTAMP
                """)

                conn.commit()

            finally:

                cur.close()
                conn.close()

        except Exception:

            pass

        await asyncio.sleep(5)
