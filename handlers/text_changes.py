import contextvars
import json
import re
from datetime import datetime
from copy import deepcopy

from telegram import (
    MessageEntity,
    Update,
    User,
)
from telegram.ext import (
    ApplicationHandlerStop,
    ContextTypes,
    ExtBot,
)

from database import connect
from handlers.roles import get_rank_level


# ==================================================
# الجلسات
# ==================================================

_text_change_sessions = {}


# ==================================================
# المستخدم الحالي الذي تسبب في إرسال رسالة البوت
# ==================================================

_text_change_actor = contextvars.ContextVar(
    "text_change_actor",
    default=None,
)


# ==================================================
# منع اعتراض رسائل النظام نفسه
# ==================================================

_text_change_internal = contextvars.ContextVar(
    "text_change_internal",
    default=False,
)


# ==================================================
# الكاش
# ==================================================

_text_changes_cache = []
_known_bot_texts = set()


# ==================================================
# المتغيرات
# ==================================================

TEXT_VARIABLES = (
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


# ==================================================
# إنشاء الجدول
# ==================================================

def create_text_changes_table():
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS text_changes (
            id BIGSERIAL PRIMARY KEY,
            old_text TEXT NOT NULL UNIQUE,
            new_text TEXT NOT NULL,
            new_entities TEXT,
            old_custom_emojis TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    conn.commit()
    cur.close()
    conn.close()

    load_text_changes()


# ==================================================
# تحميل التغييرات
# ==================================================

def load_text_changes():
    global _text_changes_cache

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            old_text,
            new_text,
            new_entities,
            old_custom_emojis
        FROM text_changes
        ORDER BY id ASC
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    _text_changes_cache = []

    for row in rows:
        (
            row_id,
            old_text,
            new_text,
            new_entities,
            old_custom_emojis,
        ) = row

        _text_changes_cache.append(
            {
                "id": row_id,
                "old_text": old_text,
                "new_text": new_text,
                "new_entities": new_entities,
                "old_custom_emojis": old_custom_emojis,
            }
        )


# ==================================================
# هل توجد تغييرات؟
# ==================================================

def has_text_changes():
    return bool(_text_changes_cache)


# ==================================================
# تطبيع المسافات
# ==================================================

def normalize_spaces(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ==================================================
# UTF-16 map
# ==================================================

def utf16_map(text):
    mapping = [0]

    for index, char in enumerate(text):
        units = len(
            char.encode("utf-16-le")
        ) // 2

        for _ in range(units):
            mapping.append(index + 1)

    return mapping


# ==================================================
# Entity UTF-16 -> Python
# ==================================================

def entity_python_range(text, entity):
    mapping = utf16_map(text)

    start_utf16 = entity.offset
    end_utf16 = (
        entity.offset +
        entity.length
    )

    if start_utf16 >= len(mapping):
        return None

    if end_utf16 >= len(mapping):
        end_utf16 = len(mapping) - 1

    return (
        mapping[start_utf16],
        mapping[end_utf16],
    )


# ==================================================
# نسخ Entity
# ==================================================

def clone_entity(
    entity,
    offset,
    length,
):
    kwargs = {}

    if getattr(entity, "url", None):
        kwargs["url"] = entity.url

    if getattr(entity, "user", None):
        kwargs["user"] = entity.user

    if getattr(entity, "language", None):
        kwargs["language"] = entity.language

    if getattr(entity, "custom_emoji_id", None):
        kwargs["custom_emoji_id"] = (
            entity.custom_emoji_id
        )

    if getattr(entity, "date_time_format", None):
        kwargs["date_time_format"] = (
            entity.date_time_format
        )

    if getattr(entity, "unix_time", None):
        kwargs["unix_time"] = entity.unix_time

    return MessageEntity(
        type=entity.type,
        offset=offset,
        length=length,
        **kwargs,
    )


# ==================================================
# حفظ Entities
# ==================================================

def serialize_entities(entities):
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

        if entity.date_time_format:
            item["date_time_format"] = (
                entity.date_time_format
            )

        if entity.unix_time:
            item["unix_time"] = (
                entity.unix_time.isoformat()
            )

        if entity.user:
            item["user"] = {
                "id": entity.user.id,
                "first_name": (
                    entity.user.first_name
                    or "مستخدم"
                ),
                "last_name": (
                    entity.user.last_name
                    if entity.user.last_name
                    else None
                ),
                "username": (
                    entity.user.username
                    if entity.user.username
                    else None
                ),
                "is_bot": bool(
                    entity.user.is_bot
                ),
            }

        result.append(item)

    return json.dumps(
        result,
        ensure_ascii=False,
    )


# ==================================================
# استرجاع Entities
# ==================================================

def deserialize_entities(data):
    if not data:
        return []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return []

    result = []

    for item in data:
        kwargs = {}

        if item.get("url"):
            kwargs["url"] = item["url"]

        if item.get("language"):
            kwargs["language"] = (
                item["language"]
            )

        if item.get("custom_emoji_id"):
            kwargs["custom_emoji_id"] = (
                item["custom_emoji_id"]
            )

        if item.get("date_time_format"):
            kwargs["date_time_format"] = (
                item["date_time_format"]
            )

        if item.get("unix_time"):
            try:
                kwargs["unix_time"] = (
                    datetime.fromisoformat(
                        item["unix_time"]
                    )
                )
            except Exception:
                pass

        user_data = item.get("user")

        if user_data:
            kwargs["user"] = User(
                id=user_data["id"],
                first_name=(
                    user_data.get(
                        "first_name"
                    )
                    or "مستخدم"
                ),
                last_name=user_data.get(
                    "last_name"
                ),
                username=user_data.get(
                    "username"
                ),
                is_bot=bool(
                    user_data.get(
                        "is_bot",
                        False,
                    )
                ),
            )

        result.append(
            MessageEntity(
                type=item["type"],
                offset=item["offset"],
                length=item["length"],
                **kwargs,
            )
        )

    return result


# ==================================================
# Custom Emoji
# ==================================================

def get_custom_emoji_signature(
    text,
    entities,
):
    result = []

    for entity in entities or []:
        if entity.type != MessageEntity.CUSTOM_EMOJI:
            continue

        entity_range = entity_python_range(
            text,
            entity,
        )

        if not entity_range:
            continue

        start, end = entity_range

        result.append(
            {
                "start": start,
                "end": end,
                "id": (
                    entity.custom_emoji_id
                    or ""
                ),
            }
        )

    result.sort(
        key=lambda x: (
            x["start"],
            x["end"],
            x["id"],
        )
    )

    return result


# ==================================================
# تطبيع النص مع خريطة المواقع
# ==================================================

def normalize_with_map(text):
    chars = []
    starts = []
    ends = []

    index = 0

    while index < len(text):

        if text[index].isspace():
            end = index + 1

            while (
                end < len(text)
                and text[end].isspace()
            ):
                end += 1

            if chars and chars[-1] != " ":
                chars.append(" ")
                starts.append(index)
                ends.append(end)

            index = end
            continue

        chars.append(text[index])
        starts.append(index)
        ends.append(index + 1)

        index += 1

    while chars and chars[0] == " ":
        chars.pop(0)
        starts.pop(0)
        ends.pop(0)

    while chars and chars[-1] == " ":
        chars.pop()
        starts.pop()
        ends.pop()

    return (
        "".join(chars),
        starts,
        ends,
    )


# ==================================================
# إيجاد التطابقات
# ==================================================

def find_matches(
    text,
    old_text,
    old_custom_emojis,
    entities,
):
    normalized_text, starts, ends = (
        normalize_with_map(text)
    )

    normalized_old = normalize_spaces(
        old_text
    )

    if not normalized_old:
        return []

    matches = []
    position = 0

    while True:

        found = normalized_text.find(
            normalized_old,
            position,
        )

        if found == -1:
            break

        normalized_end = (
            found +
            len(normalized_old)
        )

        start = starts[found]
        end = ends[
            normalized_end - 1
        ]

        current_signature = []

        valid = True

        for entity in entities or []:

            if entity.type != MessageEntity.CUSTOM_EMOJI:
                continue

            entity_range = entity_python_range(
                text,
                entity,
            )

            if not entity_range:
                continue

            entity_start, entity_end = (
                entity_range
            )

            overlaps = (
                entity_start < end
                and entity_end > start
            )

            if not overlaps:
                continue

            if (
                entity_start < start
                or entity_end > end
            ):
                valid = False
                break

            current_signature.append(
                {
                    "start": (
                        entity_start - start
                    ),
                    "end": (
                        entity_end - start
                    ),
                    "id": (
                        entity.custom_emoji_id
                        or ""
                    ),
                }
            )

        if valid:
            current_signature.sort(
                key=lambda x: (
                    x["start"],
                    x["end"],
                    x["id"],
                )
            )

            expected_signature = (
                old_custom_emojis or []
            )

            if (
                current_signature
                == expected_signature
            ):
                matches.append(
                    (start, end)
                )

        position = (
            found +
            len(normalized_old)
        )

    return matches


# ==================================================
# تجهيز المتغيرات
# ==================================================

async def prepare_new_text(
    text,
    entities,
    actor,
):
    if not actor:
        return text, entities

    if not any(
        variable in text
        for variable in TEXT_VARIABLES
    ):
        return text, entities

    try:
        from handlers.replies import (
            get_reply_user_data,
        )

        messages, rank, points = (
            await get_reply_user_data(
                actor,
                content=text,
                caption=None,
            )
        )

    except Exception:
        messages = 0
        rank = "عضو"
        points = 0

    replacements = {
        "#الاسم": (
            actor.first_name
            or "مستخدم"
        ),
        "#يوزره": (
            f"@{actor.username}"
            if actor.username
            else "لا يوجد"
        ),
        "#اليوزر": (
            f"@{actor.username}"
            if actor.username
            else "لا يوجد"
        ),
        "#الرسائل": str(messages),
        "#الايدي": str(actor.id),
        "#الرتبه": rank,
        "#التعديل": "0",
        "#النقاط": str(points),
        "#منشن": (
            actor.first_name
            or "مستخدم"
        ),
    }

    return replace_variables(
        text,
        entities,
        replacements,
        actor,
    )


# ==================================================
# استبدال المتغيرات
# ==================================================

def replace_variables(
    text,
    entities,
    replacements,
    actor,
):
    found = []

    for token in TEXT_VARIABLES:

        start = 0

        while True:

            index = text.find(
                token,
                start,
            )

            if index == -1:
                break

            found.append(
                (
                    index,
                    index + len(token),
                    token,
                )
            )

            start = (
                index +
                len(token)
            )

    if not found:
        return text, entities

    found.sort(
        key=lambda x: (
            x[0],
            -(x[1] - x[0]),
        )
    )

    selected = []
    last_end = -1

    for item in found:
        start, end, token = item

        if start < last_end:
            continue

        selected.append(item)
        last_end = end

    parts = []
    replacement_ranges = []

    cursor = 0
    output_length = 0

    for start, end, token in selected:

        before = text[cursor:start]

        parts.append(before)
        output_length += len(before)

        replacement = replacements.get(
            token,
            token,
        )

        replacement_start = output_length

        parts.append(replacement)
        output_length += len(replacement)

        replacement_ranges.append(
            (
                start,
                end,
                replacement_start,
                output_length,
                token,
            )
        )

        cursor = end

    parts.append(text[cursor:])

    new_text = "".join(parts)

    old_entity_ranges = []

    for entity in entities or []:

        entity_range = entity_python_range(
            text,
            entity,
        )

        if not entity_range:
            continue

        old_entity_ranges.append(
            (
                entity,
                entity_range[0],
                entity_range[1],
            )
        )

    new_entities = []

    # نحافظ على Entities القديمة فقط إذا لم
    # تكن داخل الجزء الذي تم استبداله
    for entity, start, end in old_entity_ranges:

        intersects_replacement = False

        for (
            token_start,
            token_end,
            replacement_start,
            replacement_end,
            token,
        ) in replacement_ranges:

            if (
                start < token_end
                and end > token_start
            ):
                intersects_replacement = True
                break

        if intersects_replacement:
            continue

        delta = 0

        for (
            token_start,
            token_end,
            replacement_start,
            replacement_end,
            token,
        ) in replacement_ranges:

            if end <= token_start:
                break

            delta += (
                (replacement_end - replacement_start)
                - (token_end - token_start)
            )

        new_start = start + delta
        new_end = end + delta

        new_entities.append(
            clone_entity(
                entity,
                new_start,
                new_end - new_start,
            )
        )

    # #منشن = Mention حقيقي
    for (
        token_start,
        token_end,
        replacement_start,
        replacement_end,
        token,
    ) in replacement_ranges:

        if token == "#منشن":
            new_entities.append(
                MessageEntity(
                    type=MessageEntity.TEXT_MENTION,
                    offset=replacement_start,
                    length=(
                        replacement_end
                        - replacement_start
                    ),
                    user=actor,
                )
            )

    new_entities = (
        MessageEntity.adjust_message_entities_to_utf_16(
            new_text,
            new_entities,
        )
    )

    return (
        new_text,
        new_entities,
    )


# ==================================================
# تطبيق تغيير واحد
# ==================================================

async def apply_one_change(
    text,
    entities,
    row,
    actor,
):
    old_text = row["old_text"]
    replacement_text = row["new_text"]

    old_custom_emojis = []

    if row["old_custom_emojis"]:
        try:
            old_custom_emojis = json.loads(
                row["old_custom_emojis"]
            )
        except Exception:
            old_custom_emojis = []

    matches = find_matches(
        text,
        old_text,
        old_custom_emojis,
        entities,
    )

    if not matches:
        return (
            text,
            entities,
            False,
        )

    replacement_text, replacement_entities = (
        await prepare_new_text(
            replacement_text,
            deserialize_entities(
                row["new_entities"]
            ),
            actor,
        )
    )

    replacement_entity_ranges = []

    for entity in replacement_entities or []:

        entity_range = entity_python_range(
            replacement_text,
            entity,
        )

        if not entity_range:
            continue

        replacement_entity_ranges.append(
            (
                entity,
                entity_range[0],
                entity_range[1],
            )
        )

    old_entity_ranges = []

    for entity in entities or []:

        entity_range = entity_python_range(
            text,
            entity,
        )

        if not entity_range:
            continue

        old_entity_ranges.append(
            (
                entity,
                entity_range[0],
                entity_range[1],
            )
        )

    output_parts = []
    output_entities = []

    output_length = 0
    cursor = 0

    def append_original(
        segment_start,
        segment_end,
    ):
        nonlocal output_length

        if segment_end <= segment_start:
            return

        segment = text[
            segment_start:segment_end
        ]

        base = output_length

        output_parts.append(segment)

        for (
            entity,
            entity_start,
            entity_end,
        ) in old_entity_ranges:

            if (
                entity_end <= segment_start
                or entity_start >= segment_end
            ):
                continue

            clipped_start = max(
                entity_start,
                segment_start,
            )

            clipped_end = min(
                entity_end,
                segment_end,
            )

            if clipped_end <= clipped_start:
                continue

            new_start = (
                base +
                clipped_start -
                segment_start
            )

            new_end = (
                base +
                clipped_end -
                segment_start
            )

            output_entities.append(
                clone_entity(
                    entity,
                    new_start,
                    new_end - new_start,
                )
            )

        output_length += len(segment)

    for match_start, match_end in matches:

        append_original(
            cursor,
            match_start,
        )

        replacement_base = output_length

        output_parts.append(
            replacement_text
        )

        for (
            entity,
            entity_start,
            entity_end,
        ) in replacement_entity_ranges:

            output_entities.append(
                clone_entity(
                    entity,
                    replacement_base + entity_start,
                    entity_end - entity_start,
                )
            )

        output_length += len(
            replacement_text
        )

        cursor = match_end

    append_original(
        cursor,
        len(text),
    )

    result_text = "".join(
        output_parts
    )

    result_entities = (
        MessageEntity.adjust_message_entities_to_utf_16(
            result_text,
            output_entities,
        )
    )

    return (
        result_text,
        result_entities,
        True,
    )


# ==================================================
# تطبيق جميع التغييرات
# ==================================================

async def transform_text(
    text,
    entities=None,
):
    if not text:
        return text, entities

    actor = _text_change_actor.get()

    current_text = text
    current_entities = list(
        entities or []
    )

    _known_bot_texts.add(text)

    for row in list(
        _text_changes_cache
    ):

        (
            current_text,
            current_entities,
            changed,
        ) = await apply_one_change(
            current_text,
            current_entities,
            row,
            actor,
        )

    _known_bot_texts.add(
        current_text
    )

    return (
        current_text,
        current_entities,
    )


# ==================================================
# تسجيل الشخص الذي تسبب في الرد
# ==================================================

async def register_text_change_actor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    actor = update.effective_user

    if actor:
        _text_change_actor.set(actor)


# ==================================================
# الصلاحية
# ==================================================

def can_change_text(update: Update):
    user = update.effective_user

    if not user:
        return False

    chat = update.effective_chat

    chat_id = (
        chat.id
        if chat
        else None
    )

    try:
        level = get_rank_level(
            user.id,
            chat_id,
        )
    except Exception:
        return False

    return level >= 6


# ==================================================
# البحث عن تغيير موجود
# ==================================================

def find_existing_change(old_text):
    normalized = normalize_spaces(
        old_text
    )

    for row in _text_changes_cache:

        if normalize_spaces(
            row["old_text"]
        ) == normalized:
            return row

    for row in _text_changes_cache:

        if normalize_spaces(
            row["new_text"]
        ) == normalized:
            return row

    return None


# ==================================================
# هل النص موجود في رسائل البوت؟
# ==================================================

def known_bot_text_contains(old_text):
    normalized_old = normalize_spaces(
        old_text
    )

    if not normalized_old:
        return False

    for bot_text in _known_bot_texts:

        if normalized_old in normalize_spaces(
            bot_text
        ):
            return True

    return False


# ==================================================
# رد داخلي بدون تعديل
# ==================================================

async def internal_reply(
    message,
    text,
):
    token = _text_change_internal.set(True)

    try:
        await message.reply_text(text)
    finally:
        _text_change_internal.reset(token)


# ==================================================
# أمر تغيير كلمة
# ==================================================

async def text_change_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not can_change_text(update):
        return

    user = update.effective_user

    if not user:
        return

    _text_change_sessions[user.id] = {
        "step": "old",
    }

    if not update.message:
        return

    await internal_reply(
        update.message,
        "• حسنًا، ارسل الكلمة الحالية .",
    )

    raise ApplicationHandlerStop()


# ==================================================
# جلسة تغيير كلمة
# ==================================================

async def text_change_session(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if not user:
        return

    session = _text_change_sessions.get(
        user.id
    )

    if not session:
        return

    message = update.message

    if not message:
        raise ApplicationHandlerStop()

    # ==================================================
    # القديمة
    # ==================================================

    if session["step"] == "old":

        if not message.text:
            raise ApplicationHandlerStop()

        old_text = message.text

        existing = find_existing_change(
            old_text
        )

        known = (
            existing is not None
            or known_bot_text_contains(
                old_text
            )
        )

        if not known:

            _text_change_sessions.pop(
                user.id,
                None,
            )

            await internal_reply(
                message,
                "• ياحبيبي الكلمة مب موجودة تاكد من الكلمة او اكتبه بالشكل الصحيح تمامًا .",
            )

            raise ApplicationHandlerStop()

        session["old_text"] = old_text

        session["old_entities"] = (
            serialize_entities(
                message.entities
            )
        )

        session["step"] = "new"

        await internal_reply(
            message,
            "• تمام، الحين ارسل الكلمة الجديدة .",
        )

        raise ApplicationHandlerStop()

    # ==================================================
    # الجديدة
    # ==================================================

    if session["step"] == "new":

        if not message.text:
            raise ApplicationHandlerStop()

        old_text = session["old_text"]
        new_text = message.text

        old_entities = deserialize_entities(
            session.get("old_entities")
        )

        old_custom_emojis = (
            get_custom_emoji_signature(
                old_text,
                old_entities,
            )
        )

        new_entities = serialize_entities(
            message.entities
        )

        existing = find_existing_change(
            old_text
        )

        conn = connect()
        cur = conn.cursor()

        if existing:

            cur.execute(
                """
                UPDATE text_changes
                SET
                    new_text = ?,
                    new_entities = ?,
                    updated_at = NOW()
                WHERE id = ?
                """,
                (
                    new_text,
                    new_entities,
                    existing["id"],
                ),
            )

        else:

            cur.execute(
                """
                INSERT INTO text_changes (
                    old_text,
                    new_text,
                    new_entities,
                    old_custom_emojis
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    old_text,
                    new_text,
                    new_entities,
                    json.dumps(
                        old_custom_emojis,
                        ensure_ascii=False,
                    ),
                ),
            )

        conn.commit()

        cur.close()
        conn.close()

        load_text_changes()

        _text_change_sessions.pop(
            user.id,
            None,
        )

        await internal_reply(
            message,
            "• تم تعديل الكلمة بنجاح .",
        )

        raise ApplicationHandlerStop()


# ==================================================
# تغيير arguments
# ==================================================

def set_argument(
    args,
    kwargs,
    index,
    name,
    value,
):
    if name in kwargs:
        kwargs[name] = value
        return args, kwargs

    if len(args) > index:
        args[index] = value
        return args, kwargs

    kwargs[name] = value

    return args, kwargs


# ==================================================
# تعديل نص + Entities
# ==================================================

async def _transform_argument_text(
    args,
    kwargs,
    text_index,
    text_name,
    entity_index=None,
    entity_name=None,
    parse_mode_index=None,
):
    args = list(args)

    text = kwargs.get(text_name)

    if text is None and len(args) > text_index:
        text = args[text_index]

    if not isinstance(text, str):
        return args, kwargs

    entities = None

    if entity_name:
        entities = kwargs.get(entity_name)

    if (
        entities is None
        and entity_index is not None
        and len(args) > entity_index
    ):
        entities = args[entity_index]

    new_text, new_entities = (
        await transform_text(
            text,
            entities,
        )
    )

    changed = (
        new_text != text
        or list(new_entities or [])
        != list(entities or [])
    )

    if not changed:
        return args, kwargs

    args, kwargs = set_argument(
        args,
        kwargs,
        text_index,
        text_name,
        new_text,
    )

    if entity_name:
        args, kwargs = set_argument(
            args,
            kwargs,
            entity_index,
            entity_name,
            new_entities or None,
        )

    if parse_mode_index is not None:
        args, kwargs = set_argument(
            args,
            kwargs,
            parse_mode_index,
            "parse_mode",
            None,
        )

    return args, kwargs


# ==================================================
# Bot مخصص
# ==================================================

class TextChangeBot(ExtBot):

    # ==================================================
    # الرسائل النصية
    # ==================================================

    async def send_message(
        self,
        *args,
        **kwargs,
    ):
        if not _text_change_internal.get():

            args, kwargs = (
                await _transform_argument_text(
                    args,
                    kwargs,
                    text_index=1,
                    text_name="text",
                    entity_index=5,
                    entity_name="entities",
                    parse_mode_index=2,
                )
            )

        return await super().send_message(
            *args,
            **kwargs,
        )

    # ==================================================
    # تعديل رسالة نصية
    # ==================================================

    async def edit_message_text(
        self,
        *args,
        **kwargs,
    ):
        if not _text_change_internal.get():

            args, kwargs = (
                await _transform_argument_text(
                    args,
                    kwargs,
                    text_index=2,
                    text_name="text",
                    entity_index=4,
                    entity_name="entities",
                    parse_mode_index=3,
                )
            )

        return await super().edit_message_text(
            *args,
            **kwargs,
        )

    # ==================================================
    # Caption
    # ==================================================

    async def edit_message_caption(
        self,
        *args,
        **kwargs,
    ):
        if not _text_change_internal.get():

            args, kwargs = (
                await _transform_argument_text(
                    args,
                    kwargs,
                    text_index=2,
                    text_name="caption",
                    entity_index=4,
                    entity_name="caption_entities",
                    parse_mode_index=3,
                )
            )

        return await super().edit_message_caption(
            *args,
            **kwargs,
        )


# ==================================================
# تغليف طرق Media
# ==================================================

def _wrap_caption_method(
    method_name,
):
    original = getattr(
        TextChangeBot,
        method_name,
    )

    async def wrapped(
        self,
        *args,
        **kwargs,
    ):
        if not _text_change_internal.get():

            args, kwargs = (
                await _transform_argument_text(
                    args,
                    kwargs,
                    text_index=2,
                    text_name="caption",
                    entity_index=4,
                    entity_name="caption_entities",
                    parse_mode_index=3,
                )
            )

        return await original(
            self,
            *args,
            **kwargs,
        )

    return wrapped


for _method_name in (
    "send_photo",
    "send_video",
    "send_animation",
    "send_audio",
    "send_document",
    "send_voice",
    "send_live_photo",
    "send_paid_media",
):
    if hasattr(TextChangeBot, _method_name):
        setattr(
            TextChangeBot,
            _method_name,
            _wrap_caption_method(
                _method_name
            ),
        )


# ==================================================
# Media Group
# ==================================================

async def _transform_media_item(
    media,
):
    try:
        caption = getattr(
            media,
            "caption",
            None,
        )

        if not isinstance(
            caption,
            str,
        ):
            return media

        entities = getattr(
            media,
            "caption_entities",
            None,
        )

        new_caption, new_entities = (
            await transform_text(
                caption,
                entities,
            )
        )

        if (
            new_caption == caption
            and list(new_entities or [])
            == list(entities or [])
        ):
            return media

        item = deepcopy(media)

        item.caption = new_caption
        item.caption_entities = (
            new_entities or None
        )

        # حتى لا يعيد Telegram تطبيق
        # parse_mode على النص بعد تحويله
        if hasattr(item, "parse_mode"):
            item.parse_mode = None

        return item

    except Exception:
        return media


async def _transform_media_list(
    media,
):
    if not media:
        return media

    result = []

    for item in media:
        result.append(
            await _transform_media_item(
                item
            )
        )

    return result


_original_send_media_group = (
    TextChangeBot.send_media_group
)


async def _send_media_group(
    self,
    *args,
    **kwargs,
):
    if not _text_change_internal.get():

        args = list(args)

        media = kwargs.get("media")

        if media is None and len(args) > 1:
            media = args[1]

        if media:
            new_media = (
                await _transform_media_list(
                    media
                )
            )

            args, kwargs = set_argument(
                args,
                kwargs,
                1,
                "media",
                new_media,
            )

        # Caption مستقل إن تم تمريره
        args, kwargs = (
            await _transform_argument_text(
                args,
                kwargs,
                text_index=7,
                text_name="caption",
                entity_index=8,
                entity_name="caption_entities",
                parse_mode_index=7,
            )
        )

    return await _original_send_media_group(
        self,
        *args,
        **kwargs,
    )


TextChangeBot.send_media_group = (
    _send_media_group
)


# ==================================================
# الاستطلاعات
# ==================================================

_original_send_poll = (
    TextChangeBot.send_poll
)


async def _send_poll(
    self,
    *args,
    **kwargs,
):
    if not _text_change_internal.get():

        args = list(args)

        # السؤال
        question = kwargs.get(
            "question"
        )

        if question is None and len(args) > 1:
            question = args[1]

        if isinstance(question, str):

            new_question, new_entities = (
                await transform_text(
                    question,
                    kwargs.get(
                        "question_entities"
                    ),
                )
            )

            if new_question != question:

                args, kwargs = set_argument(
                    args,
                    kwargs,
                    1,
                    "question",
                    new_question,
                )

                if "question_entities" in kwargs:
                    kwargs[
                        "question_entities"
                    ] = (
                        new_entities
                        or None
                    )

        # الشرح
        explanation = kwargs.get(
            "explanation"
        )

        if isinstance(
            explanation,
            str,
        ):

            new_explanation, new_entities = (
                await transform_text(
                    explanation,
                    kwargs.get(
                        "explanation_entities"
                    ),
                )
            )

            if (
                new_explanation
                != explanation
            ):
                kwargs[
                    "explanation"
                ] = new_explanation

                kwargs[
                    "explanation_entities"
                ] = (
                    new_entities
                    or None
                )

    return await _original_send_poll(
        self,
        *args,
        **kwargs,
    )


TextChangeBot.send_poll = (
    _send_poll
)


# ==================================================
# send_message_draft
# ==================================================

if hasattr(
    TextChangeBot,
    "send_message_draft",
):

    _original_send_message_draft = (
        TextChangeBot.send_message_draft
    )

    async def _send_message_draft(
        self,
        *args,
        **kwargs,
    ):
        if not _text_change_internal.get():

            args, kwargs = (
                await _transform_argument_text(
                    args,
                    kwargs,
                    text_index=1,
                    text_name="text",
                    entity_index=4,
                    entity_name="entities",
                    parse_mode_index=3,
                )
            )

        return await _original_send_message_draft(
            self,
            *args,
            **kwargs,
        )

    TextChangeBot.send_message_draft = (
        _send_message_draft
    )
