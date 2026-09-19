import datetime
import re

from html import escape

from telegram import (
    Update,
    MessageEntity,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

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


def _level(user_id):
    if is_primary_developer(user_id):
        return 6

    if is_secondary_developer(user_id):
        return 6

    return RANKS.get(
        get_rank(user_id),
        0
    )


def _can_manage(actor_id, target_id):
    if actor_id == target_id:
        return False

    if is_primary_developer(actor_id):
        return True

    if target_id == OWNER_ID:
        return False

    if is_secondary_developer(actor_id):
        if is_secondary_developer(target_id):
            return False

        return True

    return _level(actor_id) > _level(target_id)


def _can_admin(actor_id):
    return _level(actor_id) >= 2


def _can_primary_admin(actor_id):
    return _level(actor_id) >= 3


def _ensure_tables():
    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS moderation_settings (
                chat_id BIGINT PRIMARY KEY,
                durations_enabled INTEGER DEFAULT 0,
                reasons_enabled INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_mutes (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                username TEXT,
                first_name TEXT,
                by_user BIGINT,
                until_time TEXT,
                reason TEXT,
                created_at TEXT,
                UNIQUE(chat_id, user_id)
            )
            """
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _get_settings(chat_id):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT durations_enabled, reasons_enabled
            FROM moderation_settings
            WHERE chat_id=?
            """,
            (chat_id,)
        )

        row = cur.fetchone()

        if not row:
            cur.execute(
                """
                INSERT INTO moderation_settings
                (
                    chat_id,
                    durations_enabled,
                    reasons_enabled
                )
                VALUES (?,?,?)
                """,
                (chat_id, 0, 0)
            )

            conn.commit()

            return False, False

        return bool(row[0]), bool(row[1])

    finally:
        cur.close()
        conn.close()


def _set_setting(chat_id, column, value):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled,
                reasons_enabled
            )
            VALUES (?,?,?)
            ON CONFLICT(chat_id)
            DO UPDATE SET
            durations_enabled = CASE
                WHEN ? = 'durations_enabled'
                THEN ?
                ELSE moderation_settings.durations_enabled
            END,
            reasons_enabled = CASE
                WHEN ? = 'reasons_enabled'
                THEN ?
                ELSE moderation_settings.reasons_enabled
            END
            """,
            (
                chat_id,
                value if column == "durations_enabled" else 0,
                value if column == "reasons_enabled" else 0,
                column,
                value,
                column,
                value,
            )
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


def _parse_duration(value):
    if not value:
        return None

    match = re.fullmatch(
        r"(\d+)(ث|د|س|ي)",
        value.strip()
    )

    if not match:
        return None

    number = int(match.group(1))
    unit = match.group(2)

    if number <= 0:
        return None

    if unit == "ث":
        seconds = number

    elif unit == "د":
        seconds = number * 60

    elif unit == "س":
        seconds = number * 60 * 60

    else:
        seconds = number * 24 * 60 * 60

    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=seconds)
    )


def _duration_text(value):
    if not value:
        return None

    try:
        target = datetime.datetime.fromisoformat(
            value
        )

        if target.tzinfo is None:
            target = target.replace(
                tzinfo=datetime.timezone.utc
            )

        seconds = int(
            (
                target
                - datetime.datetime.now(
                    datetime.timezone.utc
                )
            ).total_seconds()
        )

        if seconds <= 0:
            return None

        if seconds < 60:
            return f"{seconds} ثانية"

        minutes = seconds // 60

        if minutes < 60:
            return f"{minutes} دقيقة"

        hours = minutes // 60

        if hours < 24:
            return f"{hours} ساعة"

        days = hours // 24

        return f"{days} يوم"

    except Exception:
        return None


def _target_from_user(user):
    return user


async def get_target(update, context):
    if not update.message:
        return None

    message = update.message

    if message.reply_to_message:
        return message.reply_to_message.from_user

    text = message.text or ""
    parts = text.split()

    if len(parts) < 2:
        return None

    value = parts[1].strip()

    if value.isdigit():
        user_id = int(value)

        try:
            info = await context.bot.get_chat(
                user_id
            )

            return info

        except Exception:
            class User:
                pass

            user = User()
            user.id = user_id
            user.first_name = str(user_id)
            user.username = None

            return user

    if value.startswith("@"):
        try:
            return await context.bot.get_chat(
                value
            )
        except Exception:
            return None

    return None


def _get_extra_parts(update):
    text = update.message.text or ""
    parts = text.split()

    if len(parts) <= 1:
        return []

    return parts[1:]


async def _check_target_is_bot(update, context, target):
    bot = await context.bot.get_me()

    if target and target.id == bot.id:
        await update.message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )
        return True

    return False


def _mention_text(user):
    name = (
        getattr(user, "first_name", None)
        or str(user.id)
    )

    username = getattr(
        user,
        "username",
        None
    )

    if username:
        return (
            f"@{username}",
            []
        )

    text = name

    entity = MessageEntity(
        type="text_mention",
        offset=0,
        length=len(
            text.encode("utf-16-le")
        ) // 2,
        user=user,
    )

    return text, [entity]


def _rank_name(user_id):
    rank = get_rank(user_id)

    return rank or "عضو"


def _build_action_message(
    action,
    target,
    actor,
    duration=None,
    reason=None,
):
    if action == "mute":
        first = "• تم كتمت الورع المزعج هذا"

    elif action == "restrict":
        first = "• والتقييد: قيدته لين يهجد بعدين فكوه"

    else:
        rank = _rank_name(actor.id)
        first = f"• تم حظرته لعيونك يا {rank}"

    name = (
        getattr(target, "first_name", None)
        or str(target.id)
    )

    username = getattr(
        target,
        "username",
        None
    )

    lines = [
        first,
        "",
        f"المستخدم ↤ {name if not username else '@' + username}",
    ]

    if duration:
        label = {
            "mute": "مدة كتمه",
            "restrict": "مدة تقييده",
            "ban": "مدة حظره",
        }.get(action, "المدة")

        lines.append(
            f"{label} ↤ {duration}"
        )

    if reason:
        lines.append(
            f"السبب ↤ {reason}"
        )

    text = "\n".join(lines)

    entities = []

    if not username:
        marker = f"المستخدم ↤ {name}"

        start = text.find(name)

        if start != -1:
            entities.append(
                MessageEntity(
                    type="text_mention",
                    offset=len(
                        text[:start]
                        .encode("utf-16-le")
                    ) // 2,
                    length=len(
                        name.encode("utf-16-le")
                    ) // 2,
                    user=target,
                )
            )

    return text, entities


async def _send_action_message(
    update,
    action,
    target,
    duration=None,
    reason=None,
):
    text, entities = _build_action_message(
        action,
        target,
        update.effective_user,
        duration,
        reason,
    )

    await update.message.reply_text(
        text,
        entities=entities or None,
    )


async def _save_bot_mute(
    chat_id,
    target,
    actor_id,
    until_date,
    reason,
):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO bot_mutes
            (
                chat_id,
                user_id,
                username,
                first_name,
                by_user,
                until_time,
                reason,
                created_at
            )
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                by_user=excluded.by_user,
                until_time=excluded.until_time,
                reason=excluded.reason
            """,
            (
                chat_id,
                target.id,
                getattr(target, "username", None),
                getattr(target, "first_name", None),
                actor_id,
                until_date.isoformat()
                if until_date
                else None,
                reason,
                datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            )
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


async def _remove_bot_mute(chat_id, user_id):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            DELETE FROM bot_mutes
            WHERE chat_id=? AND user_id=?
            """,
            (chat_id, user_id)
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


async def _is_bot_muted(chat_id, user_id):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT until_time
            FROM bot_mutes
            WHERE chat_id=? AND user_id=?
            """,
            (chat_id, user_id)
        )

        row = cur.fetchone()

    finally:
        cur.close()
        conn.close()

    if not row:
        return False

    if row[0]:
        try:
            until = datetime.datetime.fromisoformat(
                row[0]
            )

            if until.tzinfo is None:
                until = until.replace(
                    tzinfo=datetime.timezone.utc
                )

            if until <= datetime.datetime.now(
                datetime.timezone.utc
            ):
                await _remove_bot_mute(
                    chat_id,
                    user_id
                )
                return False

        except Exception:
            pass

    return True


async def delete_muted_messages(
    update,
    context
):
    if not update.message:
        return

    if not update.effective_chat:
        return

    if update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return

    if not update.effective_user:
        return

    if await _is_bot_muted(
        update.effective_chat.id,
        update.effective_user.id
    ):
        try:
            await update.message.delete()
        except Exception:
            pass


async def mute_user(update, context):
    if not update.message:
        return

    target = await get_target(
        update,
        context
    )

    if not target:
        return

    if await _check_target_is_bot(
        update,
        context,
        target
    ):
        return

    actor_id = update.effective_user.id

    if not _can_admin(actor_id):
        return

    if not _can_manage(
        actor_id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية كتم هذا الشخص"
        )
        return

    durations_enabled, reasons_enabled = (
        _get_settings(
            update.effective_chat.id
        )
    )

    parts = _get_extra_parts(update)

    until_date = None
    reason = None

    if durations_enabled and parts:
        parsed = _parse_duration(parts[0])

        if parsed:
            until_date = parsed
            parts = parts[1:]

    if reasons_enabled and parts:
        reason = " ".join(parts)

    await _save_bot_mute(
        update.effective_chat.id,
        target,
        actor_id,
        until_date,
        reason,
    )

    duration = (
        _duration_text(
            until_date.isoformat()
        )
        if until_date
        else None
    )

    await _send_action_message(
        update,
        "mute",
        target,
        duration,
        reason,
    )


async def unmute_user(update, context):
    if not update.message:
        return

    target = await get_target(
        update,
        context
    )

    if not target:
        return

    if await _check_target_is_bot(
        update,
        context,
        target
    ):
        return

    actor_id = update.effective_user.id

    if not _can_admin(actor_id):
        return

    if not _can_manage(
        actor_id,
        target.id
    ):
        return

    await _remove_bot_mute(
        update.effective_chat.id,
        target.id
    )

    await update.message.reply_text(
        f"🔊 تم رفع الكتم عن "
        f"{target.first_name}"
    )


async def restrict_user(update, context):
    if not update.message:
        return

    target = await get_target(
        update,
        context
    )

    if not target:
        return

    if await _check_target_is_bot(
        update,
        context,
        target
    ):
        return

    actor_id = update.effective_user.id

    if not _can_admin(actor_id):
        return

    if not _can_manage(
        actor_id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية تقييد هذا الشخص"
        )
        return

    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        context.bot.id
    )

    if not member.can_restrict_members:
        await update.message.reply_text(
            "❌ أعطِ البوت صلاحية تقييد الأعضاء"
        )
        return

    durations_enabled, reasons_enabled = (
        _get_settings(
            update.effective_chat.id
        )
    )

    parts = _get_extra_parts(update)

    until_date = None
    reason = None

    if durations_enabled and parts:
        parsed = _parse_duration(parts[0])

        if parsed:
            until_date = parsed
            parts = parts[1:]

    if reasons_enabled and parts:
        reason = " ".join(parts)

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False
            ),
            until_date=until_date,
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ لم أستطع تقييده.\n\n{e}"
        )
        return

    duration = (
        _duration_text(
            until_date.isoformat()
        )
        if until_date
        else None
    )

    await _send_action_message(
        update,
        "restrict",
        target,
        duration,
        reason,
    )


async def unrestrict_user(update, context):
    if not update.message:
        return

    target = await get_target(
        update,
        context
    )

    if not target:
        return

    if await _check_target_is_bot(
        update,
        context,
        target
    ):
        return

    actor_id = update.effective_user.id

    if not _can_admin(actor_id):
        return

    if not _can_manage(
        actor_id,
        target.id
    ):
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions.all_permissions(),
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ لم أستطع رفع التقييد.\n\n{e}"
        )
        return

    await update.message.reply_text(
        f"🔊 تم رفع التقييد عن "
        f"{target.first_name}"
    )


async def ban_user(update, context):
    if not update.message:
        return

    target = await get_target(
        update,
        context
    )

    if not target:
        return

    if await _check_target_is_bot(
        update,
        context,
        target
    ):
        return

    actor_id = update.effective_user.id

    if not _can_admin(actor_id):
        return

    if not _can_manage(
        actor_id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية حظر هذا الشخص"
        )
        return

    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        context.bot.id
    )

    if not member.can_restrict_members:
        await update.message.reply_text(
            "❌ أعطِ البوت صلاحية الحظر"
        )
        return

    durations_enabled, reasons_enabled = (
        _get_settings(
            update.effective_chat.id
        )
    )

    parts = _get_extra_parts(update)

    until_date = None
    reason = None

    if durations_enabled and parts:
        parsed = _parse_duration(parts[0])

        if parsed:
            until_date = parsed
            parts = parts[1:]

    if reasons_enabled and parts:
        reason = " ".join(parts)

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            until_date=until_date,
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ لم أستطع حظره.\n\n{e}"
        )
        return

    duration = (
        _duration_text(
            until_date.isoformat()
        )
        if until_date
        else None
    )

    await _send_action_message(
        update,
        "ban",
        target,
        duration,
        reason,
    )


async def unban_user(update, context):
    if not update.message:
        return

    target = await get_target(
        update,
        context
    )

    if not target:
        return

    if await _check_target_is_bot(
        update,
        context,
        target
    ):
        return

    actor_id = update.effective_user.id

    if not _can_admin(actor_id):
        return

    if not _can_manage(
        actor_id,
        target.id
    ):
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            only_if_banned=False,
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ لم أستطع رفع الحظر.\n\n{e}"
        )
        return

    await update.message.reply_text(
        f"✅ تم رفع الحظر عن "
        f"{target.first_name}"
    )


async def duration_settings(update, context):
    if not update.message:
        return

    if not update.effective_chat:
        return

    if update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return

    if not _can_admin(
        update.effective_user.id
    ):
        return

    text = update.message.text.strip()

    if text == "تفعيل المدة للمشرفين":
        _set_setting(
            update.effective_chat.id,
            "durations_enabled",
            1
        )

        await update.message.reply_text(
            "• تم تفعيل المدة للمشرفين ."
        )
        return

    if text == "تعطيل المدة للمشرفين":
        _set_setting(
            update.effective_chat.id,
            "durations_enabled",
            0
        )

        await update.message.reply_text(
            "• تم تعطيل المدة للمشرفين ."
        )


async def reason_settings(update, context):
    if not update.message:
        return

    if not update.effective_chat:
        return

    if update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return

    if not _can_admin(
        update.effective_user.id
    ):
        return

    text = update.message.text.strip()

    if text == "تفعيل الاسباب":
        _set_setting(
            update.effective_chat.id,
            "reasons_enabled",
            1
        )

        await update.message.reply_text(
            "• تم تفعيل الاسباب ."
        )
        return

    if text == "تعطيل الاسباب":
        _set_setting(
            update.effective_chat.id,
            "reasons_enabled",
            0
        )

        await update.message.reply_text(
            "• تم تعطيل الاسباب ."
        )


def _list_keyboard(kind):
    labels = {
        "mute": "مسح المكتومين",
        "restrict": "مسح المقيدين",
        "ban": "مسح المحظورين",
    }

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    labels[kind],
                    callback_data=f"moderation:clear:{kind}"
                )
            ]
        ]
    )


async def _get_list(kind, chat_id):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        if kind == "mute":
            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    first_name
                FROM bot_mutes
                WHERE chat_id=?
                ORDER BY id ASC
                """,
                (chat_id,)
            )

        elif kind == "restrict":
            cur.execute(
                """
                SELECT
                    user_id
                FROM mutes
                WHERE user_id IS NOT NULL
                ORDER BY user_id ASC
                """
            )

        else:
            cur.execute(
                """
                SELECT
                    user_id
                FROM bans
                WHERE user_id IS NOT NULL
                ORDER BY user_id ASC
                """
            )

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


async def _send_list(update, context, kind):
    query = update.callback_query

    if query:
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    rows = await _get_list(
        kind,
        chat_id
    )

    names = {
        "mute": "المكتومين",
        "restrict": "المقيدين",
        "ban": "المحظورين",
    }

    title = names[kind]

    text = (
        f"• قائمة {title}\n"
        "━━━━━━━━━━━━\n"
    )

    entities = []

    for index, row in enumerate(rows, 1):
        user_id = row[0]

        username = (
            row[1]
            if kind == "mute" and len(row) > 1
            else None
        )

        first_name = (
            row[2]
            if kind == "mute" and len(row) > 2
            else str(user_id)
        )

        if username:
            display = f"@{username}"
        else:
            display = first_name or str(user_id)

        start = len(
            text.encode("utf-16-le")
        ) // 2

        text += (
            f"{index} - {display}\n"
        )

        if not username:
            entities.append(
                MessageEntity(
                    type="text_mention",
                    offset=start + 4,
                    length=len(
                        display.encode("utf-16-le")
                    ) // 2,
                    user=type(
                        "UserObject",
                        (),
                        {
                            "id": user_id,
                            "first_name": display,
                            "is_bot": False,
                        }
                    )(),
                )
            )

    markup = _list_keyboard(kind)

    if query:
        await query.edit_message_text(
            text,
            entities=entities or None,
            reply_markup=markup
        )
    else:
        await update.message.reply_text(
            text,
            entities=entities or None,
            reply_markup=markup
        )


async def moderation_list(update, context):
    if not update.message:
        return

    if not _can_admin(
        update.effective_user.id
    ):
        return

    text = update.message.text.strip()

    if text == "المكتومين":
        await _send_list(
            update,
            context,
            "mute"
        )

    elif text == "المقيدين":
        await _send_list(
            update,
            context,
            "restrict"
        )

    elif text == "المحظورين":
        await _send_list(
            update,
            context,
            "ban"
        )


async def _clear_mutes(chat_id):
    _ensure_tables()

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            DELETE FROM bot_mutes
            WHERE chat_id=?
            """,
            (chat_id,)
        )

        conn.commit()

    finally:
        cur.close()
        conn.close()


async def _clear_restrictions(chat_id, context):
    rows = await _get_list(
        "restrict",
        chat_id
    )

    for row in rows:
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=row[0],
                permissions=ChatPermissions.all_permissions()
            )
        except Exception:
            pass

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            "DELETE FROM mutes"
        )
        conn.commit()

    finally:
        cur.close()
        conn.close()


async def _clear_bans(chat_id, context):
    rows = await _get_list(
        "ban",
        chat_id
    )

    for row in rows:
        try:
            await context.bot.unban_chat_member(
                chat_id=chat_id,
                user_id=row[0],
                only_if_banned=False
            )
        except Exception:
            pass

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute(
            "DELETE FROM bans"
        )
        conn.commit()

    finally:
        cur.close()
        conn.close()


async def moderation_clear_callback(
    update,
    context
):
    query = update.callback_query

    await query.answer()

    if not query.message:
        return

    user_id = query.from_user.id
    kind = query.data.split(":")[-1]

    if kind == "ban":
        if not _can_primary_admin(user_id):
            await query.answer(
                "❌ هذا الزر للأدمن الأساسي وفوق",
                show_alert=True
            )
            return

    else:
        if not _can_admin(user_id):
            return

    chat_id = query.message.chat.id

    if kind == "mute":
        await _clear_mutes(chat_id)

        await query.edit_message_text(
            "• تم مسح المكتومين ."
        )

    elif kind == "restrict":
        await _clear_restrictions(
            chat_id,
            context
        )

        await query.edit_message_text(
            "• تم مسح المقيدين ."
        )

    elif kind == "ban":
        await _clear_bans(
            chat_id,
            context
        )

        await query.edit_message_text(
            "• تم مسح المحظورين ."
        )


async def moderation_clear_command(
    update,
    context
):
    if not update.message:
        return

    if not update.effective_chat:
        return

    if not _can_admin(
        update.effective_user.id
    ):
        return

    text = update.message.text.strip()

    if text == "مسح المحظورين":
        if not _can_primary_admin(
            update.effective_user.id
        ):
            return

        await _clear_bans(
            update.effective_chat.id,
            context
        )

        await update.message.reply_text(
            "• تم مسح المحظورين ."
        )

    elif text == "مسح المقيدين":
        await _clear_restrictions(
            update.effective_chat.id,
            context
        )

        await update.message.reply_text(
            "• تم مسح المقيدين ."
        )

    elif text == "مسح المكتومين":
        await _clear_mutes(
            update.effective_chat.id
        )

        await update.message.reply_text(
            "• تم مسح المكتومين ."
        )


async def moderation_expiry_loop(application):
    _ensure_tables()

    while True:
        try:
            conn = connect()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT chat_id, user_id, until_time
                FROM bot_mutes
                WHERE until_time IS NOT NULL
                """
            )

            mute_rows = cur.fetchall()

            cur.close()
            conn.close()

            now = datetime.datetime.now(
                datetime.timezone.utc
            )

            for chat_id, user_id, until_time in mute_rows:
                try:
                    until = datetime.datetime.fromisoformat(
                        until_time
                    )

                    if until.tzinfo is None:
                        until = until.replace(
                            tzinfo=datetime.timezone.utc
                        )

                    if until <= now:
                        await _remove_bot_mute(
                            chat_id,
                            user_id
                        )

                except Exception:
                    pass

        except Exception as e:
            print(
                f"⚠️ خطأ في فحص مدد الحماية: {e}"
            )

        await __import__("asyncio").sleep(5)
