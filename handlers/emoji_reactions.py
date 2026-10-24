import logging
import re

from telegram import Update, ReactionTypeEmoji, ReactionTypeCustomEmoji
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ApplicationHandlerStop

from database import connect, acquire_schema_lock
from handlers.roles import is_developer

logger = logging.getLogger(__name__)
_RULES_CACHE = []
_PENDING_EMOJI = {}


def ensure_emoji_reactions_table():
    conn = connect()
    cur = None
    try:
        cur = conn.cursor()
        acquire_schema_lock(conn)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emoji_reaction_rules (
                match_type TEXT NOT NULL,
                keyword TEXT NOT NULL,
                emoji TEXT NOT NULL,
                custom_emoji_id TEXT,
                created_by BIGINT NOT NULL,
                PRIMARY KEY (match_type, keyword)
            )
        """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        conn.close()
    _load_rules()


def _load_rules():
    global _RULES_CACHE
    conn = connect()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT match_type, keyword, emoji, custom_emoji_id, created_by
            FROM emoji_reaction_rules
            ORDER BY match_type, keyword
        """)
        _RULES_CACHE = [
            {
                "match_type": row[0],
                "keyword": row[1],
                "emoji": row[2],
                "custom_emoji_id": row[3],
                "created_by": row[4],
            }
            for row in cur.fetchall()
        ]
    finally:
        if cur:
            cur.close()
        conn.close()


def _save_rule(match_type, keyword, emoji, custom_id, user_id):
    conn = connect()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO emoji_reaction_rules
                (match_type, keyword, emoji, custom_emoji_id, created_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (match_type, keyword)
            DO UPDATE SET
                emoji = EXCLUDED.emoji,
                custom_emoji_id = EXCLUDED.custom_emoji_id,
                created_by = EXCLUDED.created_by
        """, (match_type, keyword, emoji, custom_id, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        conn.close()
    _load_rules()


def _delete_rule(match_type, keyword):
    conn = connect()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM emoji_reaction_rules
            WHERE match_type = ? AND keyword = ?
        """, (match_type, keyword))
        deleted = cur.rowcount > 0
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        conn.close()
    _load_rules()
    return deleted


def _custom_emoji_id(message):
    for entity in (message.entities or []):
        if entity.type == "custom_emoji":
            return entity.custom_emoji_id
    return None


def _format_list():
    normal = [r for r in _RULES_CACHE if r["match_type"] == "exact"]
    special = [r for r in _RULES_CACHE if r["match_type"] == "contains"]
    lines = ["قائمة الايموجيات المضافة بالبوت:", "", "الايموجيات العادية:"]
    if normal:
        lines.extend(f"{i} ~ {r['keyword']} {r['emoji']}" for i, r in enumerate(normal, 1))
    else:
        lines.append("لا توجد ايموجيات عادية مضافة.")
    lines.extend(["", "—————————————————————", "", "الايموجيات المميزة:"])
    if special:
        lines.extend(f"{i} ~ {r['keyword']} {r['emoji']}" for i, r in enumerate(special, 1))
    else:
        lines.append("لا توجد ايموجيات مميزة مضافة.")
    return "\n".join(lines)


async def emoji_reactions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or not chat or message.text is None:
        return

    text = message.text.strip()
    if not text:
        return

    # أوامر الإضافة والحذف والقائمة للمطورين فقط.
    is_management_command = (
        text == "الايموجيات المضافة"
        or re.match(r"^(اضف ايموجي(?: مميز)?|مسح ايموجي(?: مميز)?)(?:\s|$)", text)
    )
    if is_management_command:
        if is_developer(user.id) is None:
            return

        if text == "الايموجيات المضافة":
            await message.reply_text(_format_list())
            raise ApplicationHandlerStop

        match = re.match(r"^اضف ايموجي مميز\s+(.+)$", text)
        if match:
            _PENDING_EMOJI[user.id] = {
                "match_type": "contains",
                "keyword": match.group(1).strip(),
            }
            await message.reply_text("• تمام، ارسل الإيموجي المميز الحين…")
            raise ApplicationHandlerStop

        match = re.match(r"^اضف ايموجي\s+(.+)$", text)
        if match:
            _PENDING_EMOJI[user.id] = {
                "match_type": "exact",
                "keyword": match.group(1).strip(),
            }
            await message.reply_text("• تمام ارسل الايموجي الحين…")
            raise ApplicationHandlerStop

        match = re.match(r"^مسح ايموجي مميز\s+(.+)$", text)
        if match:
            keyword = match.group(1).strip()
            deleted = _delete_rule("contains", keyword)
            await message.reply_text(
                f"• {'تم مسح' if deleted else 'ما لقيت'} الإيموجي المميز للكلمة: {keyword}"
            )
            raise ApplicationHandlerStop

        match = re.match(r"^مسح ايموجي\s+(.+)$", text)
        if match:
            keyword = match.group(1).strip()
            deleted = _delete_rule("exact", keyword)
            await message.reply_text(
                f"• {'تم مسح' if deleted else 'ما لقيت'} الإيموجي العادي للكلمة: {keyword}"
            )
            raise ApplicationHandlerStop

        await message.reply_text(
            "الأوامر:\nاضف ايموجي الكلمة\nاضف ايموجي مميز الكلمة\n"
            "مسح ايموجي الكلمة\nمسح ايموجي مميز الكلمة\nالايموجيات المضافة"
        )
        raise ApplicationHandlerStop

    # بعد طلب الإضافة، تُحفظ الرسالة التالية من المطور كإيموجي.
    pending = _PENDING_EMOJI.get(user.id)
    if pending:
        custom_id = _custom_emoji_id(message)
        emoji = text
        if custom_id is None and (len(text) > 8 or len(text.split()) != 1):
            await message.reply_text("• ارسل إيموجي واحد فقط.")
            raise ApplicationHandlerStop
        try:
            _save_rule(
                pending["match_type"], pending["keyword"], emoji, custom_id, user.id
            )
        except Exception:
            logger.exception("تعذر حفظ قاعدة تفاعل الإيموجي")
            await message.reply_text("• صار خطأ أثناء حفظ الإيموجي، حاول مرة ثانية.")
            raise ApplicationHandlerStop
        _PENDING_EMOJI.pop(user.id, None)
        kind = "المميز" if pending["match_type"] == "contains" else "العادي"
        await message.reply_text(f"• تم حفظ الإيموجي {kind} للكلمة: {pending['keyword']} {emoji}")
        raise ApplicationHandlerStop

    # كل القواعد عامة على جميع القروبات؛ العادي يطابق الرسالة كاملة،
    # والمميز يطابق الكلمة أو العبارة داخل الرسالة.
    lowered = text.casefold()
    for rule in _RULES_CACHE:
        keyword = rule["keyword"]
        if rule["match_type"] == "exact":
            matched = lowered == keyword.casefold()
        else:
            matched = keyword.casefold() in lowered
        if not matched:
            continue
        try:
            if rule["custom_emoji_id"]:
                reaction = ReactionTypeCustomEmoji(custom_emoji_id=rule["custom_emoji_id"])
            else:
                reaction = ReactionTypeEmoji(emoji=rule["emoji"])
            await context.bot.set_message_reaction(
                chat_id=chat.id,
                message_id=message.message_id,
                reaction=[reaction],
            )

        except TelegramError as exc:
            logger.warning(
                "فشل التفاعل بالإيموجي | "
                "chat_id=%s | message_id=%s | emoji=%s | error=%s",
                chat.id,
                message.message_id,
                rule["emoji"],
                exc,
            )
        except Exception:
            logger.exception("خطأ أثناء وضع تفاعل الإيموجي")
        return
