import json
import re
from contextvars import ContextVar

from telegram import MessageEntity, User
from telegram.ext import ApplicationHandlerStop

from database import connect
from handlers.roles import get_rank_level


# ============================================================
# Actor الحالي
# الشخص الذي تسبب في إرسال رسالة البوت
# ============================================================

_current_actor = ContextVar(
    "text_change_actor",
    default=None,
)


def get_current_actor():
    return _current_actor.get()


async def register_text_change_actor(update, context):
    user = update.effective_user

    if user:
        _current_actor.set(user)


# ============================================================
# جلسات تغيير الكلمات
# ============================================================

_change_sessions = {}


# ============================================================
# إنشاء جدول التغييرات
# ============================================================

def create_text_changes_table():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS text_changes (
            id BIGSERIAL PRIMARY KEY,
            old_text TEXT NOT NULL UNIQUE,
            new_text TEXT NOT NULL,
            new_entities TEXT,
            old_custom_emojis TEXT,
            created_by BIGINT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


# ============================================================
# الصلاحية
# Dev وما فوق فقط
# ============================================================

def _has_permission(update):
    user = update.effective_user

    if not user:
        return False

    chat = update.effective_chat

    try:
        level = get_rank_level(
            user.id,
            chat.id if chat else None,
        )

        return level >= 6

    except Exception:
        return False


# ============================================================
# تجاهل اختلاف المسافات
# ============================================================

def _normalize(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# UTF-16
# Telegram MessageEntity offsets تستخدم UTF-16
# ============================================================

def _utf16_length(text):
    return len(
        text.encode("utf-16-le")
    ) // 2


def _utf16_to_python_index(text, offset):
    if offset <= 0:
        return 0

    current = 0

    for index, char in enumerate(text):
        current += _utf16_length(char)

        if current >= offset:
            return index + 1

    return len(text)


def _entity_range(text, entity):
    start = _utf16_to_python_index(
        text,
        entity.offset,
    )

    end = _utf16_to_python_index(
        text,
        entity.offset + entity.length,
    )

    return start, end


# ============================================================
# حفظ Entities الجديدة
# ============================================================

def _serialize_entities(entities):
    if not entities:
        return None

    result = []

    for entity in entities:
        item = {
            "type": entity.type,
            "offset": entity.offset,
            "length": entity.length,
        }

        if entity.url:
            item["url"] = entity.url

        if entity.language:
            item["language"] = entity.language

        if entity.custom_emoji_id:
            item["custom_emoji_id"] = (
                entity.custom_emoji_id
            )

        if entity.user:
            item["user_id"] = entity.user.id
            item["user_first_name"] = (
                entity.user.first_name or "مستخدم"
            )
            item["user_last_name"] = (
                entity.user.last_name
            )
            item["user_username"] = (
                entity.user.username
            )
            item["user_is_bot"] = (
                entity.user.is_bot
            )

        result.append(item)

    return json.dumps(
        result,
        ensure_ascii=False,
    )


def _deserialize_entities(data):
    if not data:
        return []

    try:
        items = json.loads(data)
    except Exception:
        return []

    result = []

    for item in items:
        try:
            user = None

            if item.get("user_id"):
                user = User(
                    id=item["user_id"],
                    first_name=(
                        item.get("user_first_name")
                        or "مستخدم"
                    ),
                    is_bot=bool(
                        item.get("user_is_bot", False)
                    ),
                    last_name=item.get(
                        "user_last_name"
                    ),
                    username=item.get(
                        "user_username"
                    ),
                )

            result.append(
                MessageEntity(
                    type=item["type"],
                    offset=item["offset"],
                    length=item["length"],
                    url=item.get("url"),
                    user=user,
                    language=item.get("language"),
                    custom_emoji_id=item.get(
                        "custom_emoji_id"
                    ),
                )
            )

        except Exception:
            continue

    return result


# ============================================================
# Custom Emoji
# ============================================================

def _custom_emoji_signature(
    text,
    entities,
):
    result = []

    for entity in entities or []:
        if entity.type != MessageEntity.CUSTOM_EMOJI:
            continue

        start, end = _entity_range(
            text,
            entity,
        )

        result.append({
            "start": start,
            "end": end,
            "custom_emoji_id": (
                entity.custom_emoji_id
            ),
        })

    return result


# ============================================================
# البحث عن التطابق
# ============================================================

def _find_matches(
    text,
    old_text,
):
    """
    المسافات لا تهم.
    باقي النص، ومنه الإيموجيات، يجب أن يطابق.
    """

    normalized_text = _normalize(text)
    normalized_old = _normalize(old_text)

    if not normalized_old:
        return []

    matches = []

    start = 0

    while True:
        position = normalized_text.find(
            normalized_old,
            start,
        )

        if position == -1:
            break

        # نحتاج تحويل موقع النص المطبع
        # إلى موقع النص الأصلي.
        original_start = _map_normalized_index(
            text,
            position,
        )

        original_end = _map_normalized_index(
            text,
            position + len(normalized_old),
        )

        matches.append(
            (
                original_start,
                original_end,
            )
        )

        start = position + len(normalized_old)

    return matches


def _map_normalized_index(
    original_text,
    normalized_index,
):
    """
    يرجع موقع تقريبي في النص الأصلي
    بعد إزالة اختلاف المسافات.
    """

    normalized_position = 0
    original_position = 0

    while original_position < len(original_text):

        char = original_text[
            original_position
        ]

        if char.isspace():

            while (
                original_position < len(original_text)
                and original_text[
                    original_position
                ].isspace()
            ):
                original_position += 1

            if normalized_position < normalized_index:
                normalized_position += 1

        else:
            if normalized_position >= normalized_index:
                break

            normalized_position += 1
            original_position += 1

    return original_position


# ============================================================
# قاعدة البيانات
# ============================================================

def _get_all_changes():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            old_text,
            new_text,
            new_entities,
            old_custom_emojis
        FROM text_changes
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def _find_existing_change(old_text):
    wanted = _normalize(old_text)

    rows = _get_all_changes()

    # أولًا: old_text نفسه
    for row in rows:
        if _normalize(row[1]) == wanted:
            return row

    # ثانيًا:
    # لو سبق وغيرناه من:
    # A -> B
    #
    # ثم قال:
    # تغيير كلمة
    # B
    #
    # نعدل نفس السجل إلى C.
    for row in rows:
        if _normalize(row[2]) == wanted:
            return row

    return None


def _save_change(
    old_text,
    new_text,
    old_custom_emojis,
    new_entities,
    created_by,
):
    existing = _find_existing_change(
        old_text
    )

    conn = connect()
    cur = conn.cursor()

    if existing:
        row_id = existing[0]

        cur.execute(
            """
            UPDATE text_changes
            SET
                new_text = ?,
                new_entities = ?,
                old_custom_emojis = ?,
                created_by = ?,
                updated_at = NOW()
            WHERE id = ?
            """,
            (
                new_text,
                _serialize_entities(
                    new_entities
                ),
                json.dumps(
                    old_custom_emojis,
                    ensure_ascii=False,
                ),
                created_by,
                row_id,
            ),
        )

    else:
        cur.execute(
            """
            INSERT INTO text_changes (
                old_text,
                new_text,
                new_entities,
                old_custom_emojis,
                created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                old_text,
                new_text,
                _serialize_entities(
                    new_entities
                ),
                json.dumps(
                    old_custom_emojis,
                    ensure_ascii=False,
                ),
                created_by,
            ),
        )

    conn.commit()

    cur.close()
    conn.close()


# ============================================================
# استبدال النص
# ============================================================

def _clone_entity(
    entity,
    offset,
    length,
):
    return MessageEntity(
        type=entity.type,
        offset=offset,
        length=length,
        url=entity.url,
        user=entity.user,
        language=entity.language,
        custom_emoji_id=entity.custom_emoji_id,
    )


def _apply_one_change(
    text,
    entities,
    old_text,
    new_text,
    stored_new_entities,
    old_custom_emojis,
):
    matches = _find_matches(
        text,
        old_text,
    )

    if not matches:
        return text, entities, False

    output = []
    output_entities = []

    cursor = 0

    # نشتغل من البداية للنهاية
    for match_start, match_end in matches:

        # ====================================================
        # تأكد من Custom Emoji
        # ====================================================

        current_custom = []

        for entity in entities or []:
            if entity.type != MessageEntity.CUSTOM_EMOJI:
                continue

            start, end = _entity_range(
                text,
                entity,
            )

            if (
                start >= match_start
                and end <= match_end
            ):
                current_custom.append({
                    "start": start - match_start,
                    "end": end - match_start,
                    "custom_emoji_id": (
                        entity.custom_emoji_id
                    ),
                })

        if current_custom != old_custom_emojis:
            continue

        # ====================================================
        # الجزء قبل الكلمة
        # ====================================================

        before = text[
            cursor:match_start
        ]

        before_start = cursor

        output.append(before)

        for entity in entities or []:
            start, end = _entity_range(
                text,
                entity,
            )

            if (
                start >= before_start
                and end <= match_start
            ):
                output_entities.append(
                    _clone_entity(
                        entity,
                        _utf16_length(
                            "".join(output[:-1])
                        )
                        + _utf16_length(
                            text[
                                before_start:start
                            ]
                        ),
                        _utf16_length(
                            text[
                                start:end
                            ]
                        ),
                    )
                )

        # ====================================================
        # الكلمة الجديدة
        # ====================================================

        replacement_offset = _utf16_length(
            "".join(output)
        )

        output.append(new_text)

        for entity in stored_new_entities:
            output_entities.append(
                _clone_entity(
                    entity,
                    replacement_offset
                    + entity.offset,
                    entity.length,
                )
            )

        cursor = match_end

    # ========================================================
    # الجزء الأخير
    # ========================================================

    tail = text[cursor:]

    tail_offset = _utf16_length(
        "".join(output)
    )

    output.append(tail)

    for entity in entities or []:
        start, end = _entity_range(
            text,
            entity,
        )

        if start >= cursor:
            shift = (
                tail_offset
                - _utf16_length(
                    text[:cursor]
                )
            )

            output_entities.append(
                _clone_entity(
                    entity,
                    entity.offset + shift,
                    entity.length,
                )
            )

    return (
        "".join(output),
        output_entities,
        True,
    )


# ============================================================
# المتغيرات داخل الكلمة الجديدة
# ============================================================

async def _replace_variables(
    text,
    entities,
    actor,
):
    if not actor:
        return text, entities

    if not any(
        variable in text
        for variable in (
            "#الاسم",
            "#يوزره",
            "#اليوزر",
            "#الرسائل",
            "#الايدي",
            "#الرتبه",
            "#التعديل",
            "#النقاط",
            "#منشن",
        )
    ):
        return text, entities

    # نستفيد من نظام البيانات الموجود عندك
    try:
        from handlers.replies import (
            get_reply_user_data,
        )

        messages, rank, points = (
            await get_reply_user_data(
                actor,
                text,
                None,
            )
        )

    except Exception:
        messages = 0
        rank = "عضو"
        points = 0

    username = (
        f"@{actor.username}"
        if actor.username
        else "لا يوجد"
    )

    replacements = {
        "#الاسم": actor.first_name or "مستخدم",
        "#يوزره": username,
        "#اليوزر": username,
        "#الرسائل": str(messages),
        "#الايدي": str(actor.id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points),
        "#منشن": actor.first_name or "مستخدم",
    }

    for token, replacement in replacements.items():

        while token in text:

            position = text.find(token)

            before = text[:position]
            after = text[
                position + len(token):
            ]

            old_text = text

            # نحافظ على الـentities الموجودة
            # خارج المتغير.
            new_entities = []

            token_end = (
                position + len(token)
            )

            for entity in entities or []:

                start, end = _entity_range(
                    old_text,
                    entity,
                )

                # قبل المتغير
                if end <= position:
                    new_entities.append(entity)
                    continue

                # بعد المتغير
                if start >= token_end:

                    shift = (
                        _utf16_length(
                            replacement
                        )
                        - _utf16_length(token)
                    )

                    new_entities.append(
                        _clone_entity(
                            entity,
                            entity.offset + shift,
                            entity.length,
                        )
                    )

                    continue

                # إذا كان الـentity يغطي المتغير،
                # نحافظ عليه على النص الجديد.
                new_start = start

                if start >= position:
                    new_start = position

                if end <= token_end:
                    new_end = (
                        position
                        + len(replacement)
                    )
                else:
                    new_end = (
                        end
                        + len(replacement)
                        - len(token)
                    )

                new_entities.append(
                    _clone_entity(
                        entity,
                        _utf16_length(
                            old_text[:new_start]
                        ),
                        _utf16_length(
                            old_text[new_start:new_end]
                        )
                    )
                )

            text = (
                before
                + replacement
                + after
            )

            if token == "#منشن":
                mention_offset = _utf16_length(
                    before
                )

                new_entities.append(
                    MessageEntity(
                        type=MessageEntity.TEXT_MENTION,
                        offset=mention_offset,
                        length=_utf16_length(
                            replacement
                        ),
                        user=actor,
                    )
                )

            entities = sorted(
                new_entities,
                key=lambda e: (
                    e.offset,
                    e.length,
                ),
            )

    return text, entities


# ============================================================
# تحويل رسالة البوت
# ============================================================

async def transform_bot_text(
    text,
    entities=None,
):
    if not text:
        return text, entities

    actor = get_current_actor()

    current_text = text
    current_entities = list(
        entities or []
    )

    rows = _get_all_changes()

    for row in rows:

        (
            _row_id,
            old_text,
            new_text,
            new_entities_json,
            old_custom_json,
        ) = row

        try:
            old_custom_emojis = (
                json.loads(old_custom_json)
                if old_custom_json
                else []
            )
        except Exception:
            old_custom_emojis = []

        new_entities = _deserialize_entities(
            new_entities_json
        )

        current_text, current_entities, changed = (
            _apply_one_change(
                current_text,
                current_entities,
                old_text,
                new_text,
                new_entities,
                old_custom_emojis,
            )
        )

        if changed:
            current_text, current_entities = (
                await _replace_variables(
                    current_text,
                    current_entities,
                    actor,
                )
            )

    return (
        current_text,
        current_entities,
    )


# ============================================================
# اعتراض send_message
# ============================================================

def install_text_change_interceptor(application):

    bot = application.bot

    if getattr(
        bot,
        "_text_change_installed",
        False,
    ):
        return

    original_send_message = (
        bot.send_message
    )

    async def send_message_wrapper(
        *args,
        **kwargs,
    ):
        if (
            "text" in kwargs
            and kwargs["text"]
        ):
            new_text, new_entities = (
                await transform_bot_text(
                    kwargs["text"],
                    kwargs.get("entities"),
                )
            )

            kwargs["text"] = new_text

            if new_entities:
                kwargs["entities"] = (
                    new_entities
                )
                kwargs["parse_mode"] = None

        elif len(args) >= 2 and args[1]:

            args = list(args)

            new_text, new_entities = (
                await transform_bot_text(
                    args[1],
                    kwargs.get("entities"),
                )
            )

            args[1] = new_text

            if new_entities:
                kwargs["entities"] = (
                    new_entities
                )
                kwargs["parse_mode"] = None

            args = tuple(args)

        return await original_send_message(
            *args,
            **kwargs,
        )

    bot.send_message = (
        send_message_wrapper
    )

    bot._text_change_installed = True


# ============================================================
# الأمر: تغيير كلمة / تعديل كلمة
# ============================================================

async def text_change_command(
    update,
    context,
):
    if not _has_permission(update):
        return

    user_id = update.effective_user.id

    _change_sessions[user_id] = {
        "step": "old",
    }

    await update.message.reply_text(
        "• حسنًا، ارسل الكلمة الحالية ."
    )

    # مهم جدًا:
    # لا نخلي أي Handler آخر يتعامل
    # مع رسالة "تغيير كلمة".
    raise ApplicationHandlerStop


# ============================================================
# استقبال الكلمة الحالية والجديدة
# ============================================================

async def text_change_session(
    update,
    context,
):
    user = update.effective_user

    if not user:
        return

    user_id = user.id

    session = _change_sessions.get(
        user_id
    )

    if not session:
        return

    message = update.effective_message

    if not message:
        raise ApplicationHandlerStop

    # ========================================================
    # الستكر لا يعتبر كلمة
    # ========================================================

    if message.sticker:
        raise ApplicationHandlerStop

    if not message.text:
        raise ApplicationHandlerStop

    # ========================================================
    # الكلمة القديمة
    # ========================================================

    if session["step"] == "old":

        old_text = message.text

        existing = _find_existing_change(
            old_text
        )

        if existing is None:

            _change_sessions.pop(
                user_id,
                None,
            )

            await message.reply_text(
                "• ياحبيبي الكلمة مب موجودة تاكد من الكلمة او اكتبه بالشكل الصحيح تمامًا ."
            )

            raise ApplicationHandlerStop

        # نخزن الكلمة الحالية
        # وEntities الخاصة بالـCustom Emoji
        old_custom_emojis = (
            _custom_emoji_signature(
                old_text,
                message.entities or [],
            )
        )

        session["old_text"] = old_text
        session["old_custom_emojis"] = (
            old_custom_emojis
        )

        session["step"] = "new"

        await message.reply_text(
            "• تمام، الحين ارسل الكلمة الجديدة ."
        )

        raise ApplicationHandlerStop

    # ========================================================
    # الكلمة الجديدة
    # ========================================================

    if session["step"] == "new":

        new_text = message.text

        old_text = session[
            "old_text"
        ]

        old_custom_emojis = session.get(
            "old_custom_emojis",
            [],
        )

        _save_change(
            old_text=old_text,
            new_text=new_text,
            old_custom_emojis=(
                old_custom_emojis
            ),
            new_entities=(
                message.entities or []
            ),
            created_by=user_id,
        )

        _change_sessions.pop(
            user_id,
            None,
        )

        # ما نرسل رسالة إضافية.
        # التعديل صار مباشرة.

        raise ApplicationHandlerStop
