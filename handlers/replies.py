import asyncio
import json
from telegram import ReplyParameters, Update, MessageEntity
from telegram.ext import ContextTypes
from permissions import is_admin
from database import connect
from handlers.cache import (
    get_user_data,
)
# =========================================================
# جلسات إضافة / تعديل / حذف الردود
# =========================================================
add_reply_sessions = {}
add_special_reply_sessions = {}
delete_special_reply_sessions = {}
edit_special_reply_sessions = {}
edit_reply_sessions = {}
delete_reply_sessions = {}
# =========================================================
# Cache للردود
# =========================================================
replies_cache = None
special_replies_cache = None
_replies_cache_lock = None
def _get_replies_cache_lock():
    """
    إنشاء Lock واحد فقط لتحميل الكاش.
    """
    global _replies_cache_lock
    if _replies_cache_lock is None:
        _replies_cache_lock = asyncio.Lock()
    return _replies_cache_lock
# =========================================================
# أدوات تنظيف الجلسات
# =========================================================
def clear_reply_sessions(user_id):
    """
    حذف جميع جلسات الردود للمستخدم.
    لا نحذف جلسات الأنظمة الأخرى.
    """
    add_reply_sessions.pop(user_id, None)
    add_special_reply_sessions.pop(user_id, None)
    delete_special_reply_sessions.pop(user_id, None)
    edit_special_reply_sessions.pop(user_id, None)
    edit_reply_sessions.pop(user_id, None)
    delete_reply_sessions.pop(user_id, None)
# =========================================================
# حفظ Message Entities
# =========================================================
def serialize_entities(
    entities,
    message=None
):
    """
    حفظ جميع Message Entities الموجودة في الرسالة.
    يدعم:
    - Bold
    - Italic
    - Underline
    - Strikethrough
    - Spoiler
    - Blockquote
    - Expandable Blockquote
    - Code
    - Pre
    - Text Link
    - Text Mention
    - URL
    - Mention
    - Hashtag
    - Cashtag
    - Bot Command
    - Email
    - Phone
    - Custom Emoji
    بالإضافة إلى custom_emoji_id للإيموجي المميز.
    """
    if not entities and not message:
        return None
    serialized = []
    for entity in (entities or []):
        item = {
            "type": entity.type,
            "offset": entity.offset,
            "length": entity.length,
        }
        # -------------------------------------------------
        # Custom Emoji
        # -------------------------------------------------
        if entity.custom_emoji_id:
            item["custom_emoji_id"] = (
                entity.custom_emoji_id
            )
        # -------------------------------------------------
        # Text Link
        # -------------------------------------------------
        if entity.url:
            item["url"] = entity.url
        # -------------------------------------------------
        # Text Mention
        # -------------------------------------------------
        if entity.user:
            item["user_id"] = entity.user.id
        # -------------------------------------------------
        # Pre language
        # -------------------------------------------------
        if entity.language:
            item["language"] = entity.language
        serialized.append(item)
    # -----------------------------------------------------
    # إذا لم توجد Entities ولكن لا توجد رسالة أيضًا
    # -----------------------------------------------------
    if not serialized and not message:
        return None
    data = {
        "entities": serialized
    }
    # -----------------------------------------------------
    # حفظ مصدر الرسالة عند وجودها
    # -----------------------------------------------------
    if message:
        data.update(
            {
                "source_chat_id": message.chat.id,
                "source_message_id": message.message_id,
                "copyable": not any(
                    placeholder in (message.text or "")
                    for placeholder in (
                        "#الاسم",
                        "#يوزره",
                        "#اليوزر",
                        "#الرسائل",
                        "#الايدي",
                        "#الرتبه",
                        "#التعديل",
                        "#النقاط"
                    )
                )
            }
        )
    return json.dumps(
        data,
        ensure_ascii=False
    )
# =========================================================
# قراءة Message Entities
# =========================================================
def deserialize_entities(entities):
    """
    تحويل الـ JSON المحفوظ إلى MessageEntity objects.
    يدعم البيانات القديمة التي كانت تحفظ
    custom_emoji فقط.
    """
    if not entities:
        return None
    try:
        data = (
            json.loads(entities)
            if isinstance(entities, str)
            else entities
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError
    ):
        return None
    # -----------------------------------------------------
    # البيانات القديمة / المختلفة
    # -----------------------------------------------------
    if isinstance(data, dict):
        data = data.get("entities") or []
    if not isinstance(data, list):
        return None
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            entity_type = item["type"]
            offset = int(item["offset"])
            length = int(item["length"])
        except (
            KeyError,
            TypeError,
            ValueError
        ):
            continue
        kwargs = {}
        # -------------------------------------------------
        # Custom Emoji
        # -------------------------------------------------
        custom_emoji_id = item.get(
            "custom_emoji_id"
        )
        if custom_emoji_id:
            kwargs["custom_emoji_id"] = (
                custom_emoji_id
            )
        # -------------------------------------------------
        # Text Link
        # -------------------------------------------------
        url = item.get("url")
        if url:
            kwargs["url"] = url
        # -------------------------------------------------
        # Text Mention
        #
        # MessageEntity.user يحتاج User object،
        # لذلك لا نعيده هنا إلا إذا كانت البيانات
        # تحتاج معالجة خاصة في المستقبل.
        # -------------------------------------------------
        user_id = item.get("user_id")
        if user_id:
            # لا ننشئ User وهمي هنا.
            # Telegram entities المرسلة من الرسالة
            # يتم حفظ النوع والبيانات الأساسية.
            pass
        # -------------------------------------------------
        # Pre language
        # -------------------------------------------------
        language = item.get("language")
        if language:
            kwargs["language"] = language
        try:
            result.append(
                MessageEntity(
                    type=entity_type,
                    offset=offset,
                    length=length,
                    **kwargs
                )
            )
        except (
            TypeError,
            ValueError
        ):
            # إذا كانت Entity غير مدعومة في النسخة
            # الحالية من python-telegram-bot نتجاوزها.
            continue
    return result or None
# =========================================================
# قراءة بيانات الرد
# =========================================================
def deserialize_reply_metadata(value):
    """
    استخراج:
    entities
    source_chat_id
    source_message_id
    copyable
    """
    if not value:
        return None, None, None, False
    try:
        data = (
            json.loads(value)
            if isinstance(value, str)
            else value
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError
    ):
        return None, None, None, False
    # -----------------------------------------------------
    # بيانات قديمة كانت عبارة عن entities مباشرة
    # -----------------------------------------------------
    if not isinstance(data, dict):
        return (
            deserialize_entities(data),
            None,
            None,
            False
        )
    return (
        deserialize_entities(
            data.get("entities")
        ),
        data.get("source_chat_id"),
        data.get("source_message_id"),
        bool(
            data.get("copyable")
        )
    )
# =========================================================
# تحميل Cache الردود من DB
# =========================================================
def load_replies_cache():
    """
    تحميل الردود العادية والمميزة من قاعدة البيانات.
    هذه الدالة Sync وتستخدم عند:
    - تشغيل البوت
    - إبطال الكاش بعد تعديل الردود
    """
    global replies_cache
    global special_replies_cache
    conn = connect()
    try:
        cur = conn.cursor()
        # -------------------------------------------------
        # الردود العادية
        # -------------------------------------------------
        cur.execute(
            """
            SELECT
                name,
                text,
                type,
                caption,
                entities
            FROM replies
            """
        )
        rows = cur.fetchall()
        replies_cache = {
            row[0]: (
                row[1],
                row[2],
                row[3],
                row[4]
            )
            for row in rows
        }
        # -------------------------------------------------
        # الردود المميزة
        # -------------------------------------------------
        cur.execute(
            """
            SELECT
                name,
                text,
                type,
                caption,
                entities
            FROM special_replies
            """
        )
        special_rows = cur.fetchall()
        special_replies_cache = special_rows
        cur.close()
    finally:
        conn.close()
# =========================================================
# تحميل Cache بشكل Async
# =========================================================
async def load_replies_cache_async():
    """
    تحميل الكاش بدون إيقاف Event Loop.
    إذا كان الكاش موجودًا بالفعل:
    لا يتم الاتصال بقاعدة البيانات.
    """
    global replies_cache
    global special_replies_cache
    # -----------------------------------------------------
    # الكاش موجود
    # -----------------------------------------------------
    if (
        replies_cache is not None
        and special_replies_cache is not None
    ):
        return
    lock = _get_replies_cache_lock()
    async with lock:
        # -------------------------------------------------
        # إعادة الفحص بعد الحصول على Lock
        # -------------------------------------------------
        if (
            replies_cache is not None
            and special_replies_cache is not None
        ):
            return
        await asyncio.to_thread(
            load_replies_cache
        )
# =========================================================
# إبطال Cache
# =========================================================
def invalidate_replies_cache():
    """
    إعادة تحميل الكاش بعد:
    - إضافة رد
    - تعديل رد
    - حذف رد
    """
    load_replies_cache()
# =========================================================
# جلب Cache بشكل Sync
# =========================================================
def get_replies_cache():
    """
    دالة توافق مع أي ملفات أخرى تستعملها.
    """
    global replies_cache
    global special_replies_cache
    if (
        replies_cache is None
        or special_replies_cache is None
    ):
        load_replies_cache()
    return (
        replies_cache,
        special_replies_cache
    )
# =========================================================
# بدء إضافة رد
# =========================================================
async def add_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )
        return
    # -----------------------------------------------------
    # إلغاء جلسات الألعاب
    # -----------------------------------------------------
    try:
        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )
        add_game_sessions.pop(
            user_id,
            None
        )
        add_question_sessions.pop(
            user_id,
            None
        )
    except Exception:
        pass
    # -----------------------------------------------------
    # إلغاء جلسة رد قديمة فقط
    # -----------------------------------------------------
    add_reply_sessions.pop(
        user_id,
        None
    )
    # -----------------------------------------------------
    # بدء جلسة جديدة
    # -----------------------------------------------------
    add_reply_sessions[user_id] = {
        "step": "name"
    }
    await update.message.reply_text(
        "حسنًا، ارسل اسم الرد"
    )
# =========================================================
# إضافة الرد
# =========================================================
async def add_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    user_id = update.effective_user.id
    if user_id not in add_reply_sessions:
        return
    session = add_reply_sessions[user_id]
    # -----------------------------------------------------
    # منع تكرار أمر الإضافة
    # -----------------------------------------------------
    if update.message.text == "اضف رد":
        return
    # -----------------------------------------------------
    # اسم الرد
    # -----------------------------------------------------
    if session["step"] == "name":
        if not update.message.text:
            await update.message.reply_text(
                "❌ أرسل الاسم كنص"
            )
            return
        session["name"] = (
            update.message.text.strip()
        )
        session["step"] = "content"
        await update.message.reply_text(
            "• حسناً يمكنك اضافة\n"
            "( نص, صوره, فيديو, متحركه, بصمه, اغنيه, ملف )\n\n"
            "ويمكنك اضافة الرد بتلك الطريقة :\n\n"
            "▹ #الاسم - اسم العضو .\n"
            "▹ #يوزره - يوزر الرد .\n"
            "▹ #اليوزر - يوزر مرسل الرساله .\n"
            "▹ #الرسائل - عدد رسائل المستخدم .\n"
            "▹ #الايدي - ايدي المستخدم .\n"
            "▹ #الرتبه - رتبة المستخدم .\n"
            "▹ #التعديل - عدد تعديلات .\n"
            "▹ #النقاط - نقاط المستخدم ."
        )
        return
    # -----------------------------------------------------
    # محتوى الرد
    # -----------------------------------------------------
    if session["step"] != "content":
        return
    name = session["name"]
    content = None
    reply_type = None
    caption = None
    entities = None
    # -----------------------------------------------------
    # نص
    # -----------------------------------------------------
    if update.message.text:
        content = update.message.text
        reply_type = "text"
        entities = serialize_entities(
            update.message.entities,
            update.message
        )
    # -----------------------------------------------------
    # صورة
    # -----------------------------------------------------
    elif update.message.photo:
        content = (
            update.message.photo[-1].file_id
        )
        reply_type = "photo"
        caption = update.message.caption
    # -----------------------------------------------------
    # فيديو
    # -----------------------------------------------------
    elif update.message.video:
        content = update.message.video.file_id
        reply_type = "video"
        caption = update.message.caption
    # -----------------------------------------------------
    # متحركة
    # -----------------------------------------------------
    elif update.message.animation:
        content = (
            update.message.animation.file_id
        )
        reply_type = "animation"
        caption = update.message.caption
    # -----------------------------------------------------
    # ملصق
    # -----------------------------------------------------
    elif update.message.sticker:
        content = update.message.sticker.file_id
        reply_type = "sticker"
    # -----------------------------------------------------
    # بصمة
    # -----------------------------------------------------
    elif update.message.voice:
        content = update.message.voice.file_id
        reply_type = "voice"
    # -----------------------------------------------------
    # أغنية
    # -----------------------------------------------------
    elif update.message.audio:
        content = update.message.audio.file_id
        reply_type = "audio"
        caption = update.message.caption
    # -----------------------------------------------------
    # ملف
    # -----------------------------------------------------
    elif update.message.document:
        content = update.message.document.file_id
        reply_type = "document"
        caption = update.message.caption
    else:
        await update.message.reply_text(
            "❌ هذا النوع غير مدعوم"
        )
        return
    # -----------------------------------------------------
    # حفظ في DB
    # -----------------------------------------------------
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO replies
            (
                name,
                text,
                type,
                caption,
                entities
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (name)
            DO UPDATE SET
                text = EXCLUDED.text,
                type = EXCLUDED.type,
                caption = EXCLUDED.caption,
                entities = EXCLUDED.entities
            """,
            (
                name,
                content,
                reply_type,
                caption,
                entities
            )
        )
        conn.commit()
    finally:
        conn.close()
    # -----------------------------------------------------
    # تحديث الكاش
    # -----------------------------------------------------
    invalidate_replies_cache()
    # -----------------------------------------------------
    # إنهاء الجلسة
    # -----------------------------------------------------
    add_reply_sessions.pop(
        user_id,
        None
    )
    await update.message.reply_text(
        f"✅ تم إضافة الرد: {name}"
    )
# =========================================================
# استبدال بيانات المستخدم
# =========================================================
def replace_user_data(
    text,
    user,
    messages=0,
    rank="عضو",
    points=0
):
    """
    استبدال متغيرات الرد.
    نفس المتغيرات الموجودة في النظام القديم.
    """
    if not text:
        return text
    user_name = (
        user.first_name
        or "مستخدم"
    )
    user_username = (
        f"@{user.username}"
        if user.username
        else "لا يوجد"
    )
    text = text.replace(
        "#الاسم",
        user_name
    )
    text = text.replace(
        "#يوزره",
        user_username
    )
    text = text.replace(
        "#اليوزر",
        user_username
    )
    text = text.replace(
        "#الرسائل",
        str(messages)
    )
    text = text.replace(
        "#الايدي",
        str(user.id)
    )
    text = text.replace(
        "#الرتبه",
        rank
    )
    text = text.replace(
        "#التعديل",
        "0"
    )
    text = text.replace(
        "#النقاط",
        str(points)
    )
    return text
# =========================================================
# جلب بيانات المستخدم عند الحاجة
# =========================================================
async def get_reply_user_data(
    user,
    content=None,
    caption=None
):
    """
    لا يستدعي الكاش/DB إلا إذا كان الرد
    يحتوي على متغيرات تحتاج بيانات المستخدم.
    """
    needs_user_data = any(
        placeholder in (content or "")
        or placeholder in (caption or "")
        for placeholder in (
            "#الرسائل",
            "#الرتبه",
            "#النقاط"
        )
    )
    if not needs_user_data:
        return 0, "عضو", 0
    data = await get_user_data(
        user.id
    )
    if not data:
        return 0, "عضو", 0
    messages = (
        data.get("messages", 0)
        or 0
    )
    rank = (
        data.get("rank", "عضو")
        or "عضو"
    )
    points = (
        data.get("points", 0)
        or 0
    )
    return (
        messages,
        rank,
        points
    )
# =========================================================
# إرسال محتوى الرد
# =========================================================
async def send_reply_content(
    update,
    context,
    content,
    reply_type,
    caption=None,
    entities=None,
    source_chat_id=None,
    source_message_id=None,
    copyable=False
):
    """
    إرسال الرد حسب نوعه.
    تم فصل الإرسال في دالة واحدة حتى لا يتكرر
    نفس الكود في الردود العادية والمميزة.
    """
    if reply_type == "text":
        # -------------------------------------------------
        # محاولة النسخ الأصلي إذا كان الرد Copyable
        # -------------------------------------------------
        if (
            copyable
            and source_chat_id
            and source_message_id
        ):
            try:
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=source_chat_id,
                    message_id=source_message_id,
                    reply_parameters=ReplyParameters(
                        message_id=update.message.message_id
                    )
                )
                return
            except Exception:
                pass
        # -------------------------------------------------
        # الإرسال النصي مع Entities
        # -------------------------------------------------
        await update.message.reply_text(
            content,
            entities=entities
        )
        return
    # -----------------------------------------------------
    # صورة
    # -----------------------------------------------------
    if reply_type == "photo":
        await update.message.reply_photo(
            photo=content,
            caption=caption
        )
        return
    # -----------------------------------------------------
    # فيديو
    # -----------------------------------------------------
    if reply_type == "video":
        await update.message.reply_video(
            video=content,
            caption=caption
        )
        return
    # -----------------------------------------------------
    # متحركة
    # -----------------------------------------------------
    if reply_type == "animation":
        await update.message.reply_animation(
            animation=content,
            caption=caption
        )
        return
    # -----------------------------------------------------
    # ملصق
    # -----------------------------------------------------
    if reply_type == "sticker":
        await update.message.reply_sticker(
            sticker=content
        )
        return
    # -----------------------------------------------------
    # بصمة
    # -----------------------------------------------------
    if reply_type == "voice":
        await update.message.reply_voice(
            voice=content
        )
        return
    # -----------------------------------------------------
    # أغنية
    # -----------------------------------------------------
    if reply_type == "audio":
        await update.message.reply_audio(
            audio=content,
            caption=caption
        )
        return
    # -----------------------------------------------------
    # ملف
    # -----------------------------------------------------
    if reply_type == "document":
        await update.message.reply_document(
            document=content,
            caption=caption
        )
        return
# =========================================================
# تشغيل الردود
# =========================================================
async def check_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if not update.message.text:
        return
    message_text = (
        update.message.text.lower()
    )
    user = update.effective_user
    # =====================================================
    # تحميل Cache
    # =====================================================
    (
        replies_cache_data,
        special_replies
    ) = await load_and_get_replies_cache()
    # =====================================================
    # الردود المميزة
    # =====================================================
    for reply in special_replies:
        name = reply[0]
        content = reply[1]
        reply_type = reply[2]
        caption = reply[3]
        (
            entities,
            source_chat_id,
            source_message_id,
            copyable
        ) = deserialize_reply_metadata(
            reply[4]
        )
        if name.lower() not in message_text:
            continue
        # -------------------------------------------------
        # بيانات المستخدم
        # -------------------------------------------------
        (
            messages,
            rank,
            points
        ) = await get_reply_user_data(
            user,
            content,
            caption
        )
        content = replace_user_data(
            content,
            user,
            messages,
            rank,
            points
        )
        caption = replace_user_data(
            caption,
            user,
            messages,
            rank,
            points
        )
        # -------------------------------------------------
        # إرسال
        # -------------------------------------------------
        await send_reply_content(
            update=update,
            context=context,
            content=content,
            reply_type=reply_type,
            caption=caption,
            entities=entities,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            copyable=copyable
        )
        return
    # =====================================================
    # الردود العادية
    # =====================================================
    reply = replies_cache_data.get(
        update.message.text
    )
    if not reply:
        return
    content = reply[0]
    reply_type = reply[1]
    caption = reply[2]
    (
        entities,
        source_chat_id,
        source_message_id,
        copyable
    ) = deserialize_reply_metadata(
        reply[3]
    )
    # -----------------------------------------------------
    # بيانات المستخدم
    # -----------------------------------------------------
    (
        messages,
        rank,
        points
    ) = await get_reply_user_data(
        user,
        content,
        caption
    )
    content = replace_user_data(
        content,
        user,
        messages,
        rank,
        points
    )
    caption = replace_user_data(
        caption,
        user,
        messages,
        rank,
        points
    )
    # -----------------------------------------------------
    # إرسال
    # -----------------------------------------------------
    await send_reply_content(
        update=update,
        context=context,
        content=content,
        reply_type=reply_type,
        caption=caption,
        entities=entities,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        copyable=copyable
    )
# =========================================================
# مساعد تحميل Cache الردود
# =========================================================
async def load_and_get_replies_cache():
    await load_replies_cache_async()
    return (
        replies_cache,
        special_replies_cache
    )
# =========================================================
# قائمة الردود
# =========================================================
async def replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name
            FROM replies
            """
        )
        data = cur.fetchall()
    finally:
        conn.close()
    if not data:
        await update.message.reply_text(
            "📭 لا يوجد ردود"
        )
        return
    msg = "📋 الردود:\n\n"
    for item in data:
        msg += f"• {item[0]}\n"
    await update.message.reply_text(
        msg
    )
# =========================================================
# بدء إضافة رد مميز
# =========================================================
async def add_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    user_id = update.effective_user.id
    # -----------------------------------------------------
    # إلغاء جلسات الألعاب
    # -----------------------------------------------------
    try:
        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )
        add_game_sessions.pop(
            user_id,
            None
        )
        add_question_sessions.pop(
            user_id,
            None
        )
    except Exception:
        pass
    # -----------------------------------------------------
    # جلسة جديدة
    # -----------------------------------------------------
    add_special_reply_sessions.pop(
        user_id,
        None
    )
    add_special_reply_sessions[user_id] = {
        "step": "name"
    }
    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز"
    )
# =========================================================
# إضافة الرد المميز
# =========================================================
async def add_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if update.message.text == "اضف رد مميز":
        return
    user_id = update.effective_user.id
    if user_id not in add_special_reply_sessions:
        return
    session = add_special_reply_sessions[user_id]
    # -----------------------------------------------------
    # اسم الرد
    # -----------------------------------------------------
    if session.get("step") == "name":
        if not update.message.text:
            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )
            return
        session["name"] = (
            update.message.text.strip()
        )
        session["step"] = "content"
        await update.message.reply_text(
            "• حسناً يمكنك اضافة\n"
            "( نص, صوره, فيديو, متحركه, بصمه, اغنيه, ملف, ملصق )\n\n"
            "ويمكنك اضافة الرد بتلك الطريقة :\n\n"
            "▹ #الاسم - اسم العضو .\n"
            "▹ #يوزره - يوزر الرد .\n"
            "▹ #اليوزر - يوزر مرسل الرساله .\n"
            "▹ #الرسائل - عدد رسائل المستخدم .\n"
            "▹ #الايدي - ايدي المستخدم .\n"
            "▹ #الرتبه - رتبة المستخدم .\n"
            "▹ #التعديل - عدد تعديلات .\n"
            "▹ #النقاط - نقاط المستخدم ."
        )
        return
    # -----------------------------------------------------
    # المحتوى
    # -----------------------------------------------------
    if session.get("step") != "content":
        return
    name = session["name"]
    content = None
    reply_type = None
    caption = None
    entities = None
    if update.message.text:
        content = update.message.text
        reply_type = "text"
        entities = serialize_entities(
            update.message.entities,
            update.message
        )
    elif update.message.photo:
        content = (
            update.message.photo[-1].file_id
        )
        reply_type = "photo"
        caption = update.message.caption
    elif update.message.video:
        content = update.message.video.file_id
        reply_type = "video"
        caption = update.message.caption
    elif update.message.animation:
        content = (
            update.message.animation.file_id
        )
        reply_type = "animation"
        caption = update.message.caption
    elif update.message.sticker:
        content = update.message.sticker.file_id
        reply_type = "sticker"
    elif update.message.voice:
        content = update.message.voice.file_id
        reply_type = "voice"
    elif update.message.audio:
        content = update.message.audio.file_id
        reply_type = "audio"
    elif update.message.document:
        content = update.message.document.file_id
        reply_type = "document"
    else:
        await update.message.reply_text(
            "❌ هذا النوع غير مدعوم"
        )
        return
    # -----------------------------------------------------
    # حفظ
    # -----------------------------------------------------
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO special_replies
            (
                name,
                text,
                type,
                caption,
                entities
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (name)
            DO UPDATE SET
                text = EXCLUDED.text,
                type = EXCLUDED.type,
                caption = EXCLUDED.caption,
                entities = EXCLUDED.entities
            """,
            (
                name,
                content,
                reply_type,
                caption,
                entities
            )
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_replies_cache()
    add_special_reply_sessions.pop(
        user_id,
        None
    )
    await update.message.reply_text(
        f"⭐ تم حفظ الرد المميز: {name}"
    )
# =========================================================
# قائمة الردود المميزة
# =========================================================
async def special_replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM special_replies"
        )
        replies = cur.fetchall()
    finally:
        conn.close()
    if not replies:
        await update.message.reply_text(
            "📭 لا توجد ردود مميزة"
        )
        return
    text = (
        "⭐ قائمة الردود المميزة:\n\n"
    )
    for reply in replies:
        text += f"• {reply[0]}\n"
    await update.message.reply_text(
        text
    )
# =========================================================
# بدء حذف رد مميز
# =========================================================
async def delete_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    user_id = update.effective_user.id
    delete_special_reply_sessions[user_id] = True
    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد حذفه"
    )
# =========================================================
# حذف رد مميز
# =========================================================
async def delete_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if update.message.text == "مسح رد مميز":
        return
    user_id = update.effective_user.id
    if user_id not in delete_special_reply_sessions:
        return
    name = update.message.text.strip()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM special_replies
            WHERE name = ?
            """,
            (name,)
        )
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    invalidate_replies_cache()
    delete_special_reply_sessions.pop(
        user_id,
        None
    )
    if deleted:
        await update.message.reply_text(
            f"✅ تم حذف الرد المميز: {name}"
        )
    else:
        await update.message.reply_text(
            "❌ لم أجد رد مميز بهذا الاسم"
        )
# =========================================================
# بدء تعديل رد مميز
# =========================================================
async def edit_special_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    user_id = update.effective_user.id
    edit_special_reply_sessions[user_id] = {
        "step": "name"
    }
    await update.message.reply_text(
        "⭐ أرسل اسم الرد المميز الذي تريد تعديله"
    )
# =========================================================
# تعديل رد مميز
# =========================================================
async def edit_special_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if update.message.text == "تعديل رد مميز":
        return
    user_id = update.effective_user.id
    if user_id not in edit_special_reply_sessions:
        return
    session = edit_special_reply_sessions[user_id]
    # -----------------------------------------------------
    # اسم الرد القديم
    # -----------------------------------------------------
    if session["step"] == "name":
        if not update.message.text:
            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )
            edit_special_reply_sessions.pop(
                user_id,
                None
            )
            return
        name = update.message.text.strip()
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT name
                FROM special_replies
                WHERE name = ?
                """,
                (name,)
            )
            reply = cur.fetchone()
        finally:
            conn.close()
        if not reply:
            await update.message.reply_text(
                "❌ لا يوجد رد مميز بهذا الاسم"
            )
            edit_special_reply_sessions.pop(
                user_id,
                None
            )
            return
        session["name"] = name
        session["step"] = "content"
        await update.message.reply_text(
            "✅ تم العثور على الرد\n\n"
            "أرسل المحتوى الجديد للرد المميز"
        )
        return
    # -----------------------------------------------------
    # المحتوى الجديد
    # -----------------------------------------------------
    if session["step"] != "content":
        return
    name = session["name"]
    content = None
    reply_type = None
    caption = None
    entities = None
    if update.message.text:
        content = update.message.text
        reply_type = "text"
        entities = serialize_entities(
            update.message.entities,
            update.message
        )
    elif update.message.photo:
        content = (
            update.message.photo[-1].file_id
        )
        reply_type = "photo"
        caption = update.message.caption
    elif update.message.video:
        content = update.message.video.file_id
        reply_type = "video"
        caption = update.message.caption
    elif update.message.animation:
        content = (
            update.message.animation.file_id
        )
        reply_type = "animation"
        caption = update.message.caption
    elif update.message.sticker:
        content = update.message.sticker.file_id
        reply_type = "sticker"
    elif update.message.voice:
        content = update.message.voice.file_id
        reply_type = "voice"
    elif update.message.audio:
        content = update.message.audio.file_id
        reply_type = "audio"
        caption = update.message.caption
    elif update.message.document:
        content = update.message.document.file_id
        reply_type = "document"
        caption = update.message.caption
    else:
        await update.message.reply_text(
            "❌ هذا النوع غير مدعوم"
        )
        return
    # -----------------------------------------------------
    # تحديث DB
    # -----------------------------------------------------
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE special_replies
            SET
                text = ?,
                type = ?,
                caption = ?,
                entities = ?
            WHERE name = ?
            """,
            (
                content,
                reply_type,
                caption,
                entities,
                name
            )
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_replies_cache()
    edit_special_reply_sessions.pop(
        user_id,
        None
    )
    await update.message.reply_text(
        f"⭐ تم تعديل الرد المميز: {name}"
    )
# =========================================================
# بدء تعديل رد عادي
# =========================================================
async def edit_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    user_id = update.effective_user.id
    edit_reply_sessions[user_id] = {
        "step": "name"
    }
    await update.message.reply_text(
        "✏️ أرسل اسم الرد الذي تريد تعديله"
    )
# =========================================================
# تعديل رد عادي
# =========================================================
async def edit_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if update.message.text == "تعديل رد":
        return
    user_id = update.effective_user.id
    if user_id not in edit_reply_sessions:
        return
    session = edit_reply_sessions[user_id]
    # -----------------------------------------------------
    # اسم الرد
    # -----------------------------------------------------
    if session["step"] == "name":
        if not update.message.text:
            await update.message.reply_text(
                "❌ أرسل اسم الرد كنص"
            )
            edit_reply_sessions.pop(
                user_id,
                None
            )
            return
        name = update.message.text.strip()
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT name
                FROM replies
                WHERE name = ?
                """,
                (name,)
            )
            reply = cur.fetchone()
        finally:
            conn.close()
        if not reply:
            await update.message.reply_text(
                "❌ لا يوجد رد بهذا الاسم"
            )
            edit_reply_sessions.pop(
                user_id,
                None
            )
            return
        session["name"] = name
        session["step"] = "content"
        await update.message.reply_text(
            "✅ تم العثور على الرد\n\n"
            "أرسل المحتوى الجديد"
        )
        return
    # -----------------------------------------------------
    # المحتوى الجديد
    # -----------------------------------------------------
    if session["step"] != "content":
        return
    name = session["name"]
    content = None
    reply_type = None
    caption = None
    entities = None
    if update.message.text:
        content = update.message.text
        reply_type = "text"
        entities = serialize_entities(
            update.message.entities,
            update.message
        )
    elif update.message.photo:
        content = (
            update.message.photo[-1].file_id
        )
        reply_type = "photo"
        caption = update.message.caption
    elif update.message.video:
        content = update.message.video.file_id
        reply_type = "video"
        caption = update.message.caption
    elif update.message.animation:
        content = (
            update.message.animation.file_id
        )
        reply_type = "animation"
        caption = update.message.caption
    elif update.message.sticker:
        content = update.message.sticker.file_id
        reply_type = "sticker"
    elif update.message.voice:
        content = update.message.voice.file_id
        reply_type = "voice"
    elif update.message.audio:
        content = update.message.audio.file_id
        reply_type = "audio"
        caption = update.message.caption
    elif update.message.document:
        content = update.message.document.file_id
        reply_type = "document"
        caption = update.message.caption
    else:
        await update.message.reply_text(
            "❌ هذا النوع غير مدعوم"
        )
        return
    # -----------------------------------------------------
    # تحديث DB
    # -----------------------------------------------------
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE replies
            SET
                text = ?,
                type = ?,
                caption = ?,
                entities = ?
            WHERE name = ?
            """,
            (
                content,
                reply_type,
                caption,
                entities,
                name
            )
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_replies_cache()
    edit_reply_sessions.pop(
        user_id,
        None
    )
    await update.message.reply_text(
        f"✅ تم تعديل الرد: {name}"
    )
# =========================================================
# بدء حذف رد عادي
# =========================================================
async def delete_reply_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    user_id = update.effective_user.id
    delete_reply_sessions[user_id] = True
    await update.message.reply_text(
        "🗑️ أرسل اسم الرد الذي تريد حذفه"
    )
# =========================================================
# حذف رد عادي
# =========================================================
async def delete_reply_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if update.message.text == "مسح رد":
        return
    user_id = update.effective_user.id
    if user_id not in delete_reply_sessions:
        return
    if not update.message.text:
        return
    name = update.message.text.strip()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name
            FROM replies
            WHERE name = ?
            """,
            (name,)
        )
        reply = cur.fetchone()
        if not reply:
            return_value = False
        else:
            cur.execute(
                """
                DELETE FROM replies
                WHERE name = ?
                """,
                (name,)
            )
            return_value = True
        conn.commit()
    finally:
        conn.close()
    if not return_value:
        await update.message.reply_text(
            "❌ لا يوجد رد بهذا الاسم"
        )
        delete_reply_sessions.pop(
            user_id,
            None
        )
        return
    invalidate_replies_cache()
    delete_reply_sessions.pop(
        user_id,
        None
    )
    await update.message.reply_text(
        f"✅ تم حذف الرد: {name}"
    )
# =========================================================
# حذف جميع الردود
# =========================================================
async def delete_all_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM replies
            """
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_replies_cache()
    await update.message.reply_text(
        "✅ تم حذف جميع الردود العادية"
    )
# =========================================================
# حذف جميع الردود المميزة
# =========================================================
async def delete_all_special_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "❌ هذا الأمر للإدارة فقط"
        )
        return
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM special_replies
            """
        )
        conn.commit()
    finally:
        conn.close()
    invalidate_replies_cache()
    await update.message.reply_text(
        "⭐ تم حذف جميع الردود المميزة"
    )
