import asyncio
import re

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
    User,
)

from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import connect

from handlers.roles import (
    get_rank,
    is_primary_developer,
    is_secondary_developer,
)


OWNER_ID = 8453977662


RANKS = {
    "عضو": 0,
    "مميز": 1,
    "ادمن": 2,
    "ادمن اساسي": 3,
    "نائب المالك": 4,
    "المالك": 5,
    "Dev": 6,
}


# ==================================================
# الصلاحيات
# ==================================================

def has_permission(actor_id, target_id):

    if actor_id == target_id:
        return False

    # ==================================================
    # المطور الأساسي
    # ==================================================

    if is_primary_developer(actor_id):
        return True

    # ==================================================
    # حماية المالك
    # ==================================================

    if target_id == OWNER_ID:
        return False

    # ==================================================
    # المطور المساعد
    # ==================================================

    if is_secondary_developer(actor_id):

        if is_secondary_developer(target_id):
            return False

        return True

    # ==================================================
    # الرتب
    # ==================================================

    actor_rank = get_rank(actor_id)
    target_rank = get_rank(target_id)

    actor_level = RANKS.get(
        actor_rank,
        0,
    )

    target_level = RANKS.get(
        target_rank,
        0,
    )

    return actor_level > target_level


def has_group_permission(
    user_id,
    minimum_rank,
):

    if is_primary_developer(user_id):
        return True

    if is_secondary_developer(user_id):
        return True

    rank = get_rank(user_id)

    level = RANKS.get(
        rank,
        0,
    )

    return level >= minimum_rank


# ==================================================
# إعدادات الإشراف
# ==================================================

def get_settings(chat_id):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        SELECT
            durations_enabled,
            reasons_enabled
        FROM moderation_settings
        WHERE chat_id = ?
        """, (
            chat_id,
        ))

        row = cur.fetchone()

        if not row:

            cur.execute("""
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled,
                reasons_enabled
            )
            VALUES
            (
                ?,
                0,
                0
            )
            ON CONFLICT (chat_id)
            DO NOTHING
            """, (
                chat_id,
            ))

            conn.commit()

            return {
                "durations_enabled": False,
                "reasons_enabled": False,
            }

        return {
            "durations_enabled": bool(row[0]),
            "reasons_enabled": bool(row[1]),
        }

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


async def moderation_settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    text = (
        message.text or ""
    ).strip()

    if not has_group_permission(
        user.id,
        2,
    ):
        return

    # ==================================================
    # تفعيل المدة
    # ==================================================

    if text == "تفعيل المدة للمشرفين":

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute("""
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled,
                reasons_enabled
            )
            VALUES
            (
                ?,
                1,
                0
            )
            ON CONFLICT (chat_id)
            DO UPDATE SET
                durations_enabled = 1
            """, (
                chat.id,
            ))

            conn.commit()

        finally:

            cur.close()
            conn.close()

        await message.reply_text(
            "• تم تفعيل المدة للمشرفين."
        )

        return

    # ==================================================
    # تعطيل المدة
    # ==================================================

    if text == "تعطيل المدة للمشرفين":

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute("""
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled,
                reasons_enabled
            )
            VALUES
            (
                ?,
                0,
                0
            )
            ON CONFLICT (chat_id)
            DO UPDATE SET
                durations_enabled = 0
            """, (
                chat.id,
            ))

            conn.commit()

        finally:

            cur.close()
            conn.close()

        await message.reply_text(
            "• تم تعطيل المدة للمشرفين."
        )

        return

    # ==================================================
    # تفعيل الأسباب
    # ==================================================

    if text == "تفعيل الاسباب":

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute("""
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled,
                reasons_enabled
            )
            VALUES
            (
                ?,
                0,
                1
            )
            ON CONFLICT (chat_id)
            DO UPDATE SET
                reasons_enabled = 1
            """, (
                chat.id,
            ))

            conn.commit()

        finally:

            cur.close()
            conn.close()

        await message.reply_text(
            "• تم تفعيل الأسباب للمشرفين."
        )

        return

    # ==================================================
    # تعطيل الأسباب
    # ==================================================

    if text == "تعطيل الاسباب":

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute("""
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled,
                reasons_enabled
            )
            VALUES
            (
                ?,
                0,
                0
            )
            ON CONFLICT (chat_id)
            DO UPDATE SET
                reasons_enabled = 0
            """, (
                chat.id,
            ))

            conn.commit()

        finally:

            cur.close()
            conn.close()

        await message.reply_text(
            "• تم تعطيل الأسباب للمشرفين."
        )


# ==================================================
# المدة
# ==================================================

DURATION_PATTERN = re.compile(
    r"^(\d+)"
    r"(ث|ثانية|ثواني|"
    r"د|دقيقة|دقائق|"
    r"س|ساعة|ساعات|"
    r"ي|يوم|أيام)$"
)


def parse_duration(token):

    if not token:
        return None

    token = (
        token.strip()
        .lower()
    )

    match = DURATION_PATTERN.match(
        token
    )

    if not match:
        return None

    amount = int(
        match.group(1)
    )

    unit = match.group(2)

    if amount <= 0:
        return None

    if unit in (
        "ث",
        "ثانية",
        "ثواني",
    ):

        return amount

    if unit in (
        "د",
        "دقيقة",
        "دقائق",
    ):

        return amount * 60

    if unit in (
        "س",
        "ساعة",
        "ساعات",
    ):

        return amount * 60 * 60

    return amount * 24 * 60 * 60


def format_duration(seconds):

    if not seconds:
        return ""

    seconds = int(seconds)

    days, remainder = divmod(
        seconds,
        86400,
    )

    hours, remainder = divmod(
        remainder,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    if days:

        if days == 1:
            return "يوم"

        if days == 2:
            return "يومين"

        return f"{days} أيام"

    if hours:

        if hours == 1:
            return "ساعة"

        if hours == 2:
            return "ساعتين"

        return f"{hours} ساعات"

    if minutes:

        if minutes == 1:
            return "دقيقة"

        if minutes == 2:
            return "دقيقتين"

        return f"{minutes} دقائق"

    if seconds == 1:
        return "ثانية"

    if seconds == 2:
        return "ثانيتين"

    return f"{seconds} ثانية"


# ==================================================
# إنشاء User
# ==================================================

def build_user(
    user_id,
    first_name=None,
    username=None,
    is_bot=False,
):

    return User(
        id=int(user_id),
        first_name=first_name or str(user_id),
        is_bot=is_bot,
        username=username,
    )


# ==================================================
# البحث في users
# ==================================================

def get_user_from_database(username):

    clean_username = (
        username
        .lstrip("@")
        .strip()
        .lower()
    )

    if not clean_username:
        return None

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        SELECT
            user_id,
            username,
            first_name
        FROM users
        WHERE LOWER(
            REPLACE(
                username,
                '@',
                ''
            )
        ) = ?
        LIMIT 1
        """, (
            clean_username,
        ))

        row = cur.fetchone()

        if not row:
            return None

        return build_user(
            row[0],
            row[2],
            row[1],
            False,
        )

    finally:

        cur.close()
        conn.close()


# ==================================================
# البحث في جداول العقوبات
# ==================================================

def get_moderation_user_from_database(
    chat_id,
    username,
):

    clean_username = (
        username
        .lstrip("@")
        .strip()
        .lower()
    )

    if not clean_username:
        return None

    conn = connect()
    cur = conn.cursor()

    try:

        for table in (
            "bot_mutes",
            "restrictions",
            "moderation_bans",
        ):

            cur.execute(f"""
            SELECT
                user_id,
                username,
                first_name
            FROM {table}
            WHERE chat_id = ?
            AND LOWER(
                REPLACE(
                    username,
                    '@',
                    ''
                )
            ) = ?
            LIMIT 1
            """, (
                chat_id,
                clean_username,
            ))

            row = cur.fetchone()

            if row:

                return build_user(
                    row[0],
                    row[2],
                    row[1],
                    False,
                )

        return None

    finally:

        cur.close()
        conn.close()


# ==================================================
# البحث بالـ ID من قاعدة البيانات
# ==================================================

def get_user_by_id_from_database(
    user_id,
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        SELECT
            user_id,
            username,
            first_name
        FROM users
        WHERE user_id = ?
        LIMIT 1
        """, (
            user_id,
        ))

        row = cur.fetchone()

        if row:

            return build_user(
                row[0],
                row[2],
                row[1],
                False,
            )

        return None

    finally:

        cur.close()
        conn.close()


# ==================================================
# حل المستخدم المستهدف
# ==================================================

async def resolve_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return None, []

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    # ==================================================
    # Reply
    # ==================================================

    if message.reply_to_message:

        target = (
            message.reply_to_message.from_user
        )

        if target:

            return (
                target,
                parts[1:],
            )

    # ==================================================
    # لا يوجد هدف
    # ==================================================

    if len(parts) < 2:
        return None, []

    target_text = (
        parts[1]
        .strip()
    )

    args = parts[2:]

    # ==================================================
    # ID
    # ==================================================

    if target_text.lstrip("-").isdigit():

        try:

            user_id = int(
                target_text
            )

            # --------------------------------------------------
            # Telegram
            # --------------------------------------------------

            try:

                member = (
                    await context.bot.get_chat_member(
                        chat_id=chat.id,
                        user_id=user_id,
                    )
                )

                if member and member.user:

                    return (
                        member.user,
                        args,
                    )

            except Exception:
                pass

            # --------------------------------------------------
            # users
            # --------------------------------------------------

            try:

                target = (
                    get_user_by_id_from_database(
                        user_id
                    )
                )

                if target:

                    return (
                        target,
                        args,
                    )

            except Exception:
                pass

            # --------------------------------------------------
            # المستخدم غير معروف
            # --------------------------------------------------

            return (
                build_user(
                    user_id,
                    str(user_id),
                    None,
                    False,
                ),
                args,
            )

        except Exception:
            return None, []

    # ==================================================
    # @username
    # ==================================================

    if target_text.startswith("@"):

        username = (
            target_text[1:]
            .strip()
        )

        if not username:
            return None, []

        # --------------------------------------------------
        # users
        # --------------------------------------------------

        try:

            target = (
                get_user_from_database(
                    username
                )
            )

            if target:

                return (
                    target,
                    args,
                )

        except Exception:
            pass

        # --------------------------------------------------
        # العقوبات
        # --------------------------------------------------

        try:

            target = (
                get_moderation_user_from_database(
                    chat.id,
                    username,
                )
            )

            if target:

                return (
                    target,
                    args,
                )

        except Exception:
            pass

        # --------------------------------------------------
        # Telegram
        #
        # get_chat ليس مضمونًا للمستخدم العادي،
        # لذلك نستخدمه فقط كاحتياط.
        # --------------------------------------------------

        try:

            chat_info = (
                await context.bot.get_chat(
                    f"@{username}"
                )
            )

            if getattr(
                chat_info,
                "id",
                None,
            ):

                return (
                    build_user(
                        chat_info.id,
                        getattr(
                            chat_info,
                            "first_name",
                            None,
                        ),
                        getattr(
                            chat_info,
                            "username",
                            username,
                        ),
                        getattr(
                            chat_info,
                            "is_bot",
                            False,
                        ),
                    ),
                    args,
                )

        except Exception:
            pass

        return None, []

    return None, []


# ==================================================
# منشن
# ==================================================

def mention_user(user):

    name = escape(
        user.first_name
        or user.username
        or str(user.id)
    )

    return (
        f'<a href="tg://user?id={user.id}">'
        f'{name}'
        f'</a>'
    )


# ==================================================
# تحليل المدة والسبب
# ==================================================

def parse_action_options(
    args,
    settings,
):

    duration_seconds = None
    reason = None

    remaining = list(args)

    if (
        settings["durations_enabled"]
        and remaining
    ):

        parsed = parse_duration(
            remaining[0]
        )

        if parsed:

            duration_seconds = parsed
            remaining = remaining[1:]

    if (
        settings["reasons_enabled"]
        and remaining
    ):

        reason = " ".join(
            remaining
        ).strip()

    return (
        duration_seconds,
        reason,
    )


# ==================================================
# جلب عضو Telegram
# ==================================================

async def get_chat_member_safe(
    context,
    chat_id,
    user_id,
):

    try:

        return await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=user_id,
        )

    except Exception:

        return None


# ==================================================
# التأكد من الهدف
# ==================================================

async def check_target(
    update,
    context,
    target,
    action=None,
):

    message = update.effective_message
    actor = update.effective_user
    chat = update.effective_chat

    if not message or not actor or not target:
        return False

    # ==================================================
    # البوت
    # ==================================================

    if target.is_bot:

        await message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return False

    # ==================================================
    # المطور الأساسي
    # ==================================================

    if is_primary_developer(actor.id):
        return True

    # ==================================================
    # حماية المطورين
    # ==================================================

    if (
        is_primary_developer(target.id)
        or is_secondary_developer(target.id)
    ):

        if action == "mute":

            text = (
                "• امسح عينك وشف من الي تبي "
                "تكتمه ياورع!"
            )

        elif action == "restrict":

            text = (
                "• امسح عينك وشف من الي تبي "
                "تقيده ياورع!"
            )

        elif action == "ban":

            text = (
                "• امسح عينك وشف من الي تبي "
                "تحظره ياورع!"
            )

        else:
            return False

        await message.reply_text(text)

        return False

    # ==================================================
    # نفسه
    # ==================================================

    if target.id == actor.id:
        return False

    # ==================================================
    # حماية مشرف Telegram
    # ==================================================

    if (
        action in (
            "ban",
            "restrict",
        )
        and chat
        and chat.type in (
            "group",
            "supergroup",
        )
    ):

        member = await get_chat_member_safe(
            context,
            chat.id,
            target.id,
        )

        if member and member.status in (
            "administrator",
            "creator",
        ):

            if action == "ban":
                action_text = "تحظره"
            else:
                action_text = "تقيده"

            await message.reply_text(
                f"• اعذرني بس الشخص الي تبي "
                f"{action_text} مشرف بالقروب ."
            )

            return False

    # ==================================================
    # الرتبة
    # ==================================================

    if not has_permission(
        actor.id,
        target.id,
    ):

        if action == "mute":

            text = (
                "• امسح عينك وشف من الي تبي "
                "تكتمه ياورع!"
            )

        elif action == "restrict":

            text = (
                "• امسح عينك وشف من الي تبي "
                "تقيده ياورع!"
            )

        elif action == "ban":

            text = (
                "• امسح عينك وشف من الي تبي "
                "تحظره ياورع!"
            )

        else:
            return False

        await message.reply_text(text)

        return False

    return True


# ==================================================
# الحظر
# ==================================================

async def ban_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    allowed = await check_target(
        update,
        context,
        target,
        "ban",
    )

    if not allowed:
        return

    settings = get_settings(
        chat.id
    )

    duration_seconds, reason = (
        parse_action_options(
            args,
            settings,
        )
    )

    until_time = None
    until_date = None

    if duration_seconds:

        until_date = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                seconds=duration_seconds
            )
        )

        until_time = (
            until_date.isoformat()
        )

    # ==================================================
    # Telegram Ban
    # ==================================================

    try:

        await context.bot.ban_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            until_date=until_date,
        )

    except Exception as e:

        await message.reply_text(
            "• فشل الحظر من Telegram.\n"
            f"الخطأ ↤ {escape(str(e))}",
            parse_mode="HTML",
        )

        return

    # ==================================================
    # حفظ في قاعدة البيانات
    # ==================================================

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        INSERT INTO moderation_bans
        (
            chat_id,
            user_id,
            username,
            first_name,
            until_time,
            reason,
            by_user
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        ON CONFLICT
        (
            chat_id,
            user_id
        )
        DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            until_time = EXCLUDED.until_time,
            reason = EXCLUDED.reason,
            by_user = EXCLUDED.by_user
        """, (
            chat.id,
            target.id,
            target.username,
            target.first_name,
            until_time,
            reason,
            actor.id,
        ))

        # ==================================================
        # سجل الإدارة
        # ==================================================

        cur.execute("""
        INSERT INTO moderation_logs
        (
            action,
            user_id,
            by_user,
            date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """, (
            "ban",
            target.id,
            actor.id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ))

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        cur.close()
        conn.close()

    # ==================================================
    # الرسالة
    # ==================================================

    actor_rank = get_rank(
        actor.id
    )

    text = (
        f"تم حظرته لعيونك يـ "
        f"{escape(actor_rank)}\n"
        f"المستخدم ↤ "
        f"{mention_user(target)}"
    )

    if (
        settings["durations_enabled"]
        and duration_seconds
    ):

        text += (
            f"\nمدة حظره ↤ "
            f"{format_duration(duration_seconds)}"
        )

    if (
        settings["reasons_enabled"]
        and reason
    ):

        text += (
            f"\nالسبب ↤ "
            f"{escape(reason)}"
        )

    await message.reply_text(
        text,
        parse_mode="HTML",
    )


# ==================================================
# رفع الحظر
# ==================================================

async def unban_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    if target.is_bot:

        await message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return

    if not is_primary_developer(actor.id):

        if not has_permission(
            actor.id,
            target.id,
        ):
            return

    try:

        await context.bot.unban_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            only_if_banned=True,
        )

    except Exception as e:

        await message.reply_text(
            "• فشل رفع الحظر من Telegram.\n"
            f"الخطأ ↤ {escape(str(e))}",
            parse_mode="HTML",
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        DELETE FROM moderation_bans
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            target.id,
        ))

        cur.execute("""
        INSERT INTO moderation_logs
        (
            action,
            user_id,
            by_user,
            date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """, (
            "unban",
            target.id,
            actor.id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()

    await message.reply_text(
        f"• تم رفع الحظر عن "
        f"{mention_user(target)}",
        parse_mode="HTML",
    )


# ==================================================
# الكتم البوتي
# ==================================================

async def mute_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    if not await check_target(
        update,
        context,
        target,
        "mute",
    ):
        return

    settings = get_settings(
        chat.id
    )

    duration_seconds, reason = (
        parse_action_options(
            args,
            settings,
        )
    )

    until_time = None

    if duration_seconds:

        until_time = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                seconds=duration_seconds
            )
        ).isoformat()

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        INSERT INTO bot_mutes
        (
            chat_id,
            user_id,
            username,
            first_name,
            until_time,
            reason,
            by_user
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        ON CONFLICT
        (
            chat_id,
            user_id
        )
        DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            until_time = EXCLUDED.until_time,
            reason = EXCLUDED.reason,
            by_user = EXCLUDED.by_user
        """, (
            chat.id,
            target.id,
            target.username,
            target.first_name,
            until_time,
            reason,
            actor.id,
        ))

        cur.execute("""
        INSERT INTO moderation_logs
        (
            action,
            user_id,
            by_user,
            date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """, (
            "mute",
            target.id,
            actor.id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()

    text = (
        f"• تم كتمت الورع المزعج هذا "
        f"{mention_user(target)}"
    )

    if (
        settings["durations_enabled"]
        and duration_seconds
    ):

        text += (
            f"\nمدة الكتم ↤ "
            f"{format_duration(duration_seconds)}"
        )

    if (
        settings["reasons_enabled"]
        and reason
    ):

        text += (
            f"\nالسبب ↤ "
            f"{escape(reason)}"
        )

    await message.reply_text(
        text,
        parse_mode="HTML",
    )


# ==================================================
# رفع الكتم
# ==================================================

async def unmute_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    if target.is_bot:

        await message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return

    if not is_primary_developer(actor.id):

        if not has_permission(
            actor.id,
            target.id,
        ):
            return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        DELETE FROM bot_mutes
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            target.id,
        ))

        cur.execute("""
        INSERT INTO moderation_logs
        (
            action,
            user_id,
            by_user,
            date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """, (
            "unmute",
            target.id,
            actor.id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()

    await message.reply_text(
        f"• تم رفع الكتم عن "
        f"{mention_user(target)}",
        parse_mode="HTML",
    )


# ==================================================
# التقييد
# ==================================================

async def restrict_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    if not await check_target(
        update,
        context,
        target,
        "restrict",
    ):
        return

    settings = get_settings(
        chat.id
    )

    duration_seconds, reason = (
        parse_action_options(
            args,
            settings,
        )
    )

    until_time = None
    until_date = None

    if duration_seconds:

        until_date = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                seconds=duration_seconds
            )
        )

        until_time = (
            until_date.isoformat()
        )

    # ==================================================
    # صلاحيات مقيدة بالكامل
    # ==================================================

    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_invite_users=False,
    )

    # ==================================================
    # Telegram Restrict
    # ==================================================

    try:

        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            permissions=permissions,
            until_date=until_date,
        )

    except Exception as e:

        await message.reply_text(
            "• فشل التقييد من Telegram.\n"
            f"الخطأ ↤ {escape(str(e))}",
            parse_mode="HTML",
        )

        return

    # ==================================================
    # قاعدة البيانات
    # ==================================================

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        INSERT INTO restrictions
        (
            chat_id,
            user_id,
            username,
            first_name,
            until_time,
            reason,
            by_user
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        ON CONFLICT
        (
            chat_id,
            user_id
        )
        DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            until_time = EXCLUDED.until_time,
            reason = EXCLUDED.reason,
            by_user = EXCLUDED.by_user
        """, (
            chat.id,
            target.id,
            target.username,
            target.first_name,
            until_time,
            reason,
            actor.id,
        ))

        cur.execute("""
        INSERT INTO moderation_logs
        (
            action,
            user_id,
            by_user,
            date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """, (
            "restrict",
            target.id,
            actor.id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ))

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        cur.close()
        conn.close()

    text = (
        "تم قيدته لين يهجد بعدين فكوه\n"
        f"المستخدم ↤ "
        f"{mention_user(target)}"
    )

    if (
        settings["durations_enabled"]
        and duration_seconds
    ):

        text += (
            f"\nمدة تقييده ↤ "
            f"{format_duration(duration_seconds)}"
        )

    if (
        settings["reasons_enabled"]
        and reason
    ):

        text += (
            f"\nالسبب ↤ "
            f"{escape(reason)}"
        )

    await message.reply_text(
        text,
        parse_mode="HTML",
    )


# ==================================================
# رفع التقييد
# ==================================================

async def unrestrict_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    if target.is_bot:

        await message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return

    if not is_primary_developer(actor.id):

        if not has_permission(
            actor.id,
            target.id,
        ):
            return

    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )

    try:

        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target.id,
            permissions=permissions,
        )

    except Exception as e:

        await message.reply_text(
            "• فشل رفع التقييد من Telegram.\n"
            f"الخطأ ↤ {escape(str(e))}",
            parse_mode="HTML",
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        DELETE FROM restrictions
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            target.id,
        ))

        cur.execute("""
        INSERT INTO moderation_logs
        (
            action,
            user_id,
            by_user,
            date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """, (
            "unrestrict",
            target.id,
            actor.id,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()

    await message.reply_text(
        f"• تم رفع التقييد عن "
        f"{mention_user(target)}",
        parse_mode="HTML",
    )


# ==================================================
# معلومات المستخدم
# ==================================================

async def check_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    target, args = await resolve_target(
        update,
        context,
    )

    if not target:

        await message.reply_text(
            "• ما قدرت أحدد المستخدم."
        )

        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        SELECT
            until_time,
            reason,
            by_user
        FROM bot_mutes
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            target.id,
        ))

        mute = cur.fetchone()

        cur.execute("""
        SELECT
            until_time,
            reason,
            by_user
        FROM restrictions
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            target.id,
        ))

        restriction = cur.fetchone()

        cur.execute("""
        SELECT
            until_time,
            reason,
            by_user
        FROM moderation_bans
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            target.id,
        ))

        ban = cur.fetchone()

    finally:

        cur.close()
        conn.close()

    text = (
        "• معلومات المستخدم\n"
        f"المستخدم ↤ "
        f"{mention_user(target)}"
    )

    rank = get_rank(
        target.id
    )

    if rank:

        text += (
            f"\nالرتبة ↤ "
            f"{escape(rank)}"
        )

    if mute:

        text += (
            "\n\n• الحالة ↤ مكتوم"
        )

        if mute[0]:

            text += (
                f"\nينتهي ↤ "
                f"{escape(str(mute[0]))}"
            )

        if mute[1]:

            text += (
                f"\nالسبب ↤ "
                f"{escape(str(mute[1]))}"
            )

    if restriction:

        text += (
            "\n\n• الحالة ↤ مقيد"
        )

        if restriction[0]:

            text += (
                f"\nينتهي ↤ "
                f"{escape(str(restriction[0]))}"
            )

        if restriction[1]:

            text += (
                f"\nالسبب ↤ "
                f"{escape(str(restriction[1]))}"
            )

    if ban:

        text += (
            "\n\n• الحالة ↤ محظور"
        )

        if ban[0]:

            text += (
                f"\nينتهي ↤ "
                f"{escape(str(ban[0]))}"
            )

        if ban[1]:

            text += (
                f"\nالسبب ↤ "
                f"{escape(str(ban[1]))}"
            )

    if not mute and not restriction and not ban:

        text += (
            "\n\n• الحالة ↤ "
            "لا توجد عليه عقوبة"
        )

    await message.reply_text(
        text,
        parse_mode="HTML",
    )


# ==================================================
# إعدادات القوائم
# ==================================================

LIST_CONFIG = {

    "mute": {
        "table": "bot_mutes",
        "title": "المكتومين",
        "button": "مسح المكتومين",
    },

    "restrict": {
        "table": "restrictions",
        "title": "المقيدين",
        "button": "مسح المقيدين",
    },

    "ban": {
        "table": "moderation_bans",
        "title": "المحظورين",
        "button": "مسح المحظورين",
    },
}


# ==================================================
# القوائم
# ==================================================

async def moderation_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    text = (
        message.text or ""
    ).strip()

    if text == "المكتومين":

        list_type = "mute"

    elif text == "المقيدين":

        list_type = "restrict"

    elif text == "المحظورين":

        list_type = "ban"

    else:
        return

    config = LIST_CONFIG[
        list_type
    ]

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(f"""
        SELECT
            user_id,
            username,
            first_name
        FROM {config["table"]}
        WHERE chat_id = ?
        ORDER BY user_id
        """, (
            chat.id,
        ))

        rows = cur.fetchall()

    finally:

        cur.close()
        conn.close()

    result = (
        f"• قائمه {config['title']}\n"
        " ━━━━━━━━━━━━\n"
    )

    if not rows:

        result += "لا يوجد أحد."

    else:

        lines = []

        for index, row in enumerate(
            rows,
            start=1,
        ):

            user_id = row[0]
            username = row[1]
            first_name = row[2]

            if username:

                display = (
                    f"@{escape(username)}"
                )

            else:

                fake_user = build_user(
                    user_id,
                    first_name,
                    None,
                    False,
                )

                display = mention_user(
                    fake_user
                )

            lines.append(
                f"{index} - {display}"
            )

        result += "\n".join(
            lines
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                config["button"],
                callback_data=(
                    f"modclear:{list_type}"
                ),
            )
        ]
    ])

    await message.reply_text(
        result,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# ==================================================
# مسح القوائم
# ==================================================

async def clear_moderation_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user

    if not message or not chat or not actor:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    text = (
        message.text or ""
    ).strip()

    if text == "مسح المكتومين":

        list_type = "mute"

    elif text == "مسح المقيدين":

        list_type = "restrict"

    elif text == "مسح المحظورين":

        list_type = "ban"

    else:
        return

    minimum_rank = (
        3
        if list_type == "ban"
        else 2
    )

    if not has_group_permission(
        actor.id,
        minimum_rank,
    ):
        return

    await clear_moderation(
        chat.id,
        list_type,
        context,
    )

    config = LIST_CONFIG[
        list_type
    ]

    await message.reply_text(
        f"• تم مسح {config['title']} ."
    )


# ==================================================
# تنفيذ المسح
# ==================================================

async def clear_moderation(
    chat_id,
    list_type,
    context,
):

    config = LIST_CONFIG[
        list_type
    ]

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(f"""
        SELECT user_id
        FROM {config["table"]}
        WHERE chat_id = ?
        """, (
            chat_id,
        ))

        users = cur.fetchall()

        if list_type == "ban":

            for row in users:

                try:

                    await context.bot.unban_chat_member(
                        chat_id=chat_id,
                        user_id=row[0],
                        only_if_banned=True,
                    )

                except Exception:
                    pass

        elif list_type == "restrict":

            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
            )

            for row in users:

                try:

                    await context.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=row[0],
                        permissions=permissions,
                    )

                except Exception:
                    pass

        cur.execute(f"""
        DELETE FROM {config["table"]}
        WHERE chat_id = ?
        """, (
            chat_id,
        ))

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        cur.close()
        conn.close()


# ==================================================
# أزرار القوائم
# ==================================================

async def moderation_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query or not query.message:
        return

    data = query.data or ""

    if not data.startswith(
        "modclear:"
    ):
        return

    await query.answer()

    list_type = data.split(
        ":",
        1,
    )[1]

    if list_type not in LIST_CONFIG:
        return

    actor = query.from_user
    chat = query.message.chat

    minimum_rank = (
        3
        if list_type == "ban"
        else 2
    )

    if not has_group_permission(
        actor.id,
        minimum_rank,
    ):

        await query.answer(
            "ما عندك صلاحية.",
            show_alert=True,
        )

        return

    await clear_moderation(
        chat.id,
        list_type,
        context,
    )

    title = LIST_CONFIG[
        list_type
    ]["title"]

    await query.edit_message_text(
        f"• تم مسح {title} ."
    )


# ==================================================
# حذف رسائل المكتومين
# ==================================================

async def delete_bot_muted_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (
        "group",
        "supergroup",
    ):
        return

    if user.is_bot:
        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
        SELECT until_time
        FROM bot_mutes
        WHERE chat_id = ?
        AND user_id = ?
        """, (
            chat.id,
            user.id,
        ))

        row = cur.fetchone()

        if not row:
            return

        until_time = row[0]

        if until_time:

            try:

                expiry = datetime.fromisoformat(
                    until_time
                )

                if expiry.tzinfo is None:

                    expiry = expiry.replace(
                        tzinfo=timezone.utc
                    )

                if (
                    datetime.now(
                        timezone.utc
                    )
                    >= expiry
                ):

                    cur.execute("""
                    DELETE FROM bot_mutes
                    WHERE chat_id = ?
                    AND user_id = ?
                    """, (
                        chat.id,
                        user.id,
                    ))

                    conn.commit()

                    return

            except Exception:
                pass

        try:

            await message.delete()

        except Exception:
            pass

    finally:

        cur.close()
        conn.close()

    raise ApplicationHandlerStop


# ==================================================
# تنظيف العقوبات المنتهية
# ==================================================

async def moderation_expiry_loop(
    application,
):

    while True:

        try:

            now = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            conn = connect()
            cur = conn.cursor()

            try:

                cur.execute("""
                DELETE FROM bot_mutes
                WHERE until_time IS NOT NULL
                AND until_time <= ?
                """, (
                    now,
                ))

                cur.execute("""
                DELETE FROM restrictions
                WHERE until_time IS NOT NULL
                AND until_time <= ?
                """, (
                    now,
                ))

                cur.execute("""
                DELETE FROM moderation_bans
                WHERE until_time IS NOT NULL
                AND until_time <= ?
                """, (
                    now,
                ))

                conn.commit()

            except Exception:

                conn.rollback()

            finally:

                cur.close()
                conn.close()

        except Exception:
            pass

        await asyncio.sleep(10)
