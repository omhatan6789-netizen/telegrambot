from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)
from database import connect
OWNER_ID = 8453977662
WAIT_OLD, WAIT_NEW = range(2)
add_command_sessions = {}
# ==================================================
# كاش الأوامر المضافة
# ==================================================
_custom_commands_cache = None
# ==================================================
# كاش تنفيذ الأوامر
# ==================================================
_resolved_handlers_cache = {}
# ==================================================
# حماية من الحلقة عند تشغيل الأمر الأصلي
# ==================================================
_alias_execution_keys = set()
def is_alias_execution(update):
    """
    معرفة هل هذا الـ Update يتم تشغيله داخليًا
    بواسطة أمر مضاف أم لا.
    """
    if not update or not update.message:
        return False
    key = (
        getattr(update.message, "chat_id", None),
        getattr(update.message, "message_id", None),
    )
    return key in _alias_execution_keys
def _add_alias_execution(update):
    """
    إضافة Update إلى قائمة التنفيذ الداخلي.
    """
    if not update or not update.message:
        return None
    key = (
        getattr(update.message, "chat_id", None),
        getattr(update.message, "message_id", None),
    )
    _alias_execution_keys.add(key)
    return key
def _remove_alias_execution(key):
    """
    إزالة Update من قائمة التنفيذ الداخلي.
    """
    if key is not None:
        _alias_execution_keys.discard(key)
# ==================================================
# تحميل الأوامر المضافة
# ==================================================
def load_custom_commands_cache():
    global _custom_commands_cache
    if _custom_commands_cache is not None:
        return _custom_commands_cache
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT old_command, new_command
            FROM custom_commands
            """
        )
        rows = cur.fetchall()
        _custom_commands_cache = {
            str(new).strip(): str(old).strip()
            for old, new in rows
            if old and new
        }
        return _custom_commands_cache
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
# ==================================================
# جلب الكاش
# ==================================================
def get_custom_commands_cache():
    return load_custom_commands_cache()
# ==================================================
# تحديث الكاش
# ==================================================
def invalidate_custom_commands_cache():
    global _custom_commands_cache
    _custom_commands_cache = None
    _resolved_handlers_cache.clear()
    return load_custom_commands_cache()
# ==================================================
# إضافة أمر للكاش
# ==================================================
def set_custom_command_cache(
    old_command,
    new_command
):
    global _custom_commands_cache
    if _custom_commands_cache is None:
        _custom_commands_cache = {}
    if not old_command or not new_command:
        return
    old_command = str(
        old_command
    ).strip()
    new_command = str(
        new_command
    ).strip()
    if not old_command or not new_command:
        return
    _custom_commands_cache[
        new_command
    ] = old_command
    # إزالة أي handler قديم
    _resolved_handlers_cache.pop(
        new_command,
        None
    )
# ==================================================
# حذف أمر من الكاش
# ==================================================
def remove_custom_command_cache(
    new_command
):
    global _custom_commands_cache
    if not new_command:
        return
    new_command = str(
        new_command
    ).strip()
    if _custom_commands_cache is not None:
        _custom_commands_cache.pop(
            new_command,
            None
        )
    _resolved_handlers_cache.pop(
        new_command,
        None
    )
# ==================================================
# مسح جميع الكاش
# ==================================================
def clear_custom_commands_cache():
    global _custom_commands_cache
    _custom_commands_cache = {}
    _resolved_handlers_cache.clear()
# ==================================================
# إضافة أمر
# ==================================================
async def add_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    if not update.effective_user:
        return
    if update.effective_user.id != OWNER_ID:
        return
    user_id = update.effective_user.id
    add_command_sessions[user_id] = {}
    await update.message.reply_text(
        "حسناً، أرسل الأمر القديم"
    )
    return WAIT_OLD
# ==================================================
# استقبال الأمر القديم
# ==================================================
async def receive_old_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.effective_user:
        return WAIT_OLD
    user_id = update.effective_user.id
    if user_id not in add_command_sessions:
        return WAIT_OLD
    if not update.message:
        return WAIT_OLD
    if not update.message.text:
        return WAIT_OLD
    old = update.message.text.strip()
    if not old:
        await update.message.reply_text(
            "• أرسل الأمر القديم"
        )
        return WAIT_OLD
    add_command_sessions[user_id][
        "old"
    ] = old
    await update.message.reply_text(
        "حسناً، أرسل الأمر الجديد"
    )
    return WAIT_NEW
# ==================================================
# استقبال الأمر الجديد
# ==================================================
async def receive_new_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.effective_user:
        return ConversationHandler.END
    user_id = update.effective_user.id
    if user_id not in add_command_sessions:
        return ConversationHandler.END
    if not update.message:
        return WAIT_NEW
    if not update.message.text:
        return WAIT_NEW
    new = update.message.text.strip()
    if not new:
        await update.message.reply_text(
            "• أرسل الأمر الجديد"
        )
        return WAIT_NEW
    old = add_command_sessions[user_id].get(
        "old"
    )
    if not old:
        return ConversationHandler.END
    if old == new:
        await update.message.reply_text(
            "• الأمر الجديد لازم يكون مختلف عن الأمر القديم"
        )
        return WAIT_NEW
    conn = connect()
    cur = conn.cursor()
    try:
        # إذا كان الاسم الجديد مستخدمًا من قبل نحذفه
        cur.execute(
            """
            DELETE FROM custom_commands
            WHERE new_command = ?
            """,
            (new,)
        )
        # حفظ الأمر
        cur.execute(
            """
            INSERT INTO custom_commands
            (
                old_command,
                new_command
            )
            VALUES (?, ?)
            """,
            (
                old,
                new
            )
        )
        conn.commit()
    except Exception as e:
        print(
            "❌ خطأ أثناء حفظ الأمر المضاف:",
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass
        await update.message.reply_text(
            "❌ حصل خطأ أثناء حفظ الأمر."
        )
        return WAIT_NEW
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    # تحديث الكاش مباشرة
    set_custom_command_cache(
        old,
        new
    )
    add_command_sessions.pop(
        user_id,
        None
    )
    await update.message.reply_text(
        f"✅ تم إضافة الأمر\n\n"
        f"{new} يعمل الآن مثل {old}"
    )
    return ConversationHandler.END
# ==================================================
# قائمة الأوامر
# ==================================================
async def custom_commands_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    data_cache = get_custom_commands_cache()
    data = [
        (old, new)
        for new, old in data_cache.items()
    ]
    data.sort(
        key=lambda item: item[1]
    )
    if not data:
        await update.message.reply_text(
            "لا توجد أوامر مضافة"
        )
        return
    text = "📌 الأوامر المضافة:\n\n"
    for old, new in data:
        text += (
            f"{new} ➜ {old}\n"
        )
    await update.message.reply_text(
        text
    )
# ==================================================
# بدء حذف أمر
# ==================================================
async def delete_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    context.user_data[
        "delete_command"
    ] = True
    await update.message.reply_text(
        "أرسل الأمر الجديد الذي تريد حذفه"
    )
# ==================================================
# حذف أمر
# ==================================================
async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not context.user_data.get(
        "delete_command"
    ):
        return
    if not update.message:
        return
    if not update.message.text:
        return
    command = update.message.text.strip()
    conn = connect()
    cur = conn.cursor()
    deleted = 0
    try:
        cur.execute(
            """
            DELETE FROM custom_commands
            WHERE new_command = ?
            """,
            (command,)
        )
        deleted = cur.rowcount
        conn.commit()
    except Exception as e:
        print(
            "❌ خطأ أثناء حذف الأمر:",
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass
        context.user_data.pop(
            "delete_command",
            None
        )
        await update.message.reply_text(
            "❌ حصل خطأ أثناء حذف الأمر."
        )
        return
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    # تحديث الكاش
    if deleted:
        remove_custom_command_cache(
            command
        )
    context.user_data.pop(
        "delete_command",
        None
    )
    if deleted:
        await update.message.reply_text(
            "✅ تم حذف الأمر المضاف"
        )
    else:
        await update.message.reply_text(
            "• ما لقيت هذا الأمر ضمن الأوامر المضافة"
        )
# ==================================================
# حذف جميع الأوامر
# ==================================================
async def delete_all_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM custom_commands"
        )
        conn.commit()
    except Exception as e:
        print(
            "❌ خطأ أثناء حذف جميع الأوامر:",
            e
        )
        try:
            conn.rollback()
        except Exception:
            pass
        await update.message.reply_text(
            "❌ حصل خطأ أثناء حذف الأوامر."
        )
        return
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    clear_custom_commands_cache()
    await update.message.reply_text(
        "✅ تم حذف جميع الأوامر المضافة"
    )
# ==================================================
# جلب الأمر الأصلي
# ==================================================
def get_custom_command(text):
    if not text:
        return None
    text = str(
        text
    ).strip()
    if not text:
        return None
    commands = get_custom_commands_cache()
    return commands.get(
        text
    )
# ==================================================
# إنشاء Update وهمي
# ==================================================
def _make_fake_update(
    update: Update,
    old_command: str,
    application
):
    try:
        data = update.to_dict()
        if "message" not in data:
            return None
        message_data = data["message"]
        # وضع الأمر الأصلي مكان الأمر المضاف
        message_data["text"] = old_command
        # إزالة entities القديمة
        # حتى لا تتعارض مع الأمر الجديد
        message_data.pop(
            "entities",
            None
        )
        fake_update = Update.de_json(
            data,
            application.bot
        )
        return fake_update
    except Exception as e:
        print(
            "❌ خطأ في إنشاء Update للأمر المضاف:",
            e
        )
        return None
# ==================================================
# تشغيل الأمر الأصلي داخل نظام البوت
# ==================================================
async def _process_alias_update(
    fake_update,
    application
):
    if not fake_update:
        return False
    key = _add_alias_execution(
        fake_update
    )
    try:
        # تشغيل الـ Update من خلال نظام
        # python-telegram-bot نفسه.
        #
        # هذا يجعل Telegram bot handlers
        # يتعاملون مع الأمر الأصلي بشكل طبيعي.
        await application.process_update(
            fake_update
        )
        return True
    except Exception as e:
        print(
            f"❌ خطأ أثناء تشغيل الأمر المضاف: {e}"
        )
        return False
    finally:
        _remove_alias_execution(
            key
        )
# ==================================================
# تشغيل الأمر المضاف
# ==================================================
async def check_custom_commands(
    update,
    context,
    application=None
):
    if not update:
        return False
    if not update.message:
        return False
    if not update.message.text:
        return False
    if not application:
        return False
    # إذا كان هذا Update داخليًا
    # فلا نعيد تشغيل الأوامر المضافة
    if is_alias_execution(update):
        return False
    text = update.message.text.strip()
    if not text:
        return False
    # ==================================================
    # أثناء إضافة أمر جديد
    # ==================================================
    if (
        update.effective_user
        and update.effective_user.id
        in add_command_sessions
    ):
        return False
    # ==================================================
    # أثناء حذف أمر
    # ==================================================
    if context.user_data.get(
        "delete_command"
    ):
        return False
    # ==================================================
    # البحث عن الأمر المضاف
    # ==================================================
    old_command = get_custom_command(
        text
    )
    if not old_command:
        return False
    old_command = old_command.strip()
    if not old_command:
        return False
    # ==================================================
    # منع الحلقة
    # ==================================================
    if old_command == text:
        return False
    # ==================================================
    # إنشاء Update وهمي
    # ==================================================
    fake_update = _make_fake_update(
        update,
        old_command,
        application
    )
    if not fake_update:
        return False
    # ==================================================
    # تشغيل الأمر الأصلي
    # ==================================================
    executed = await _process_alias_update(
        fake_update,
        application
    )
    if executed:
        print(
            f"✅ تم تنفيذ الأمر المضاف: "
            f"{text} -> {old_command}"
        )
        return True
    print(
        f"⚠️ تعذر تنفيذ الأمر المضاف: "
        f"{text} -> {old_command}"
    )
    return False
