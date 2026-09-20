import time
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
# 🚀 كاش الأوامر المضافة
# ==================================================
_custom_commands_cache = None
def load_custom_commands_cache():
    """
    تحميل جميع الأوامر المضافة من قاعدة البيانات مرة واحدة.
    """
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
        conn.close()
def get_custom_commands_cache():
    """
    إرجاع الكاش بدون أي استعلام جديد إذا كان محملاً.
    """
    return load_custom_commands_cache()
def invalidate_custom_commands_cache():
    """
    إعادة تحميل الكاش من قاعدة البيانات.
    تستخدم فقط بعد التعديل على الأوامر.
    """
    global _custom_commands_cache
    _custom_commands_cache = None
    _resolved_handlers_cache = {}
    return load_custom_commands_cache()
def set_custom_command_cache(old_command, new_command):
    global _custom_commands_cache

    if _custom_commands_cache is None:
        _custom_commands_cache = {}

    if old_command and new_command:
        new_command = str(new_command).strip()
        _custom_commands_cache[new_command] = str(old_command).strip()

        # إذا تغير الأمر، لا نستخدم handler قديم
        _resolved_handlers_cache.pop(new_command, None)
def remove_custom_command_cache(new_command):
    global _custom_commands_cache

    if new_command:
        new_command = str(new_command).strip()

        if _custom_commands_cache is not None:
            _custom_commands_cache.pop(new_command, None)

        _resolved_handlers_cache.pop(new_command, None)
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
    if not update.message or not update.message.text:
        return WAIT_OLD
    old = update.message.text.strip()
    if not old:
        await update.message.reply_text(
            "• أرسل الأمر القديم"
        )
        return WAIT_OLD
    add_command_sessions[user_id]["old"] = old
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
    if not update.message or not update.message.text:
        return WAIT_NEW
    new = update.message.text.strip()
    if not new:
        await update.message.reply_text(
            "• أرسل الأمر الجديد"
        )
        return WAIT_NEW
    old = add_command_sessions[user_id]["old"]
    if old == new:
        await update.message.reply_text(
            "• الأمر الجديد لازم يكون مختلف عن الأمر القديم"
        )
        return WAIT_NEW
    conn = connect()
    cur = conn.cursor()
    try:
        # حذف الاختصار القديم إن وجد
        cur.execute(
            """
            DELETE FROM custom_commands
            WHERE new_command = ?
            """,
            (new,)
        )
        # إضافة الاختصار
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
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        await update.message.reply_text(
            "❌ حصل خطأ أثناء حفظ الأمر."
        )
        return WAIT_NEW
    conn.close()
    # ==================================================
    # 🚀 تحديث الكاش مباشرة
    # ==================================================
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
    # ==================================================
    # 🚀 استخدام الكاش بدل استعلام قاعدة البيانات
    # ==================================================
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
# حذف أمر
# ==================================================
async def delete_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return
    context.user_data["delete_command"] = True
    await update.message.reply_text(
        "أرسل الأمر الجديد الذي تريد حذفه"
    )
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
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        context.user_data.pop(
            "delete_command",
            None
        )
        await update.message.reply_text(
            "❌ حصل خطأ أثناء حذف الأمر."
        )
        return
    conn.close()
    # ==================================================
    # 🚀 تحديث الكاش
    # ==================================================
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
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        await update.message.reply_text(
            "❌ حصل خطأ أثناء حذف الأوامر."
        )
        return
    conn.close()
    # ==================================================
    # 🚀 تفريغ الكاش
    # ==================================================
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
    text = text.strip()
    if not text:
        return None
    # ==================================================
    # 🚀 البحث من الكاش فقط
    # ==================================================
    commands = get_custom_commands_cache()
    return commands.get(text)
# ==================================================
# الهاندلرات العامة التي لا تعتبر أوامر بداية
# ==================================================
GENERIC_CALLBACK_NAMES = {
    "custom_command_alias_handler",
    "command_guard",
    "check_custom_commands",
    "check_speed_words",
    "check_anime_answer",
    "play_game",
    "check_game_answer",
    "check_word_race_message",
    "check_liar_message",
    "check_muted_message",
    "check_replies",
    "save_user_message",
    "add_reply_handler",
    "add_special_reply_handler",
    "edit_reply_handler",
    "edit_special_reply_handler",
    "delete_reply_handler",
    "delete_special_reply_handler",
    "add_game_handler",
    "add_question_handler",
    "change_button_color_handler",
    "whisper_private_message",
    "delete_command",
    "save_lock_rank",
    "stop_after_game",
    "profile_reply_pending_handler",
}
# ==================================================
# التحقق من Handler عام
# ==================================================
def is_generic_handler(handler):
    callback = getattr(
        handler,
        "callback",
        None
    )
    if callback is None:
        return True
    name = getattr(
        callback,
        "__name__",
        ""
    )
    return name in GENERIC_CALLBACK_NAMES
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
        message_data["text"] = old_command
        # النص تغير، لذلك نحذف entities القديمة
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
# تشغيل الأمر الأصلي
# ==================================================
async def check_custom_commands(update, context, application=None):
    if not update.message:
        return False

    if not update.message.text:
        return False

    if not application:
        return False

    text = update.message.text.strip()

    if not text:
        return False

    if (
        update.effective_user
        and update.effective_user.id in add_command_sessions
    ):
        return False

    if context.user_data.get("delete_command"):
        return False

    old_command = get_custom_command(text)

    if not old_command:
        return False

    old_command = old_command.strip()

    if not old_command:
        return False

    fake_update = _make_fake_update(
        update,
        old_command,
        application
    )

    if not fake_update:
        return False

    # =====================================================
    # إذا سبق وحددنا الـhandler لهذا الأمر
    # لا نعيد البحث في جميع الـhandlers
    # =====================================================

    handler = _resolved_handlers_cache.get(text)

    if handler is not None:

        try:
            check_result = handler.check_update(
                fake_update
            )

            if check_result:

                handler.collect_additional_context(
                    context,
                    fake_update,
                    application,
                    check_result
                )

                await handler.handle_update(
                    fake_update,
                    application,
                    check_result,
                    context
                )

                return True

        except Exception as e:

            # إذا تغير شيء في الـhandler
            # نحذف الكاش ونبحث مرة أخرى
            _resolved_handlers_cache.pop(
                text,
                None
            )

            print(
                f"❌ خطأ في تشغيل الأمر المضاف {text}: {e}"
            )

    # =====================================================
    # البحث عن الـhandler مرة واحدة فقط
    # =====================================================

    for group in sorted(application.handlers.keys()):

        handlers = application.handlers[group]

        for current_handler in handlers:

            callback = getattr(
                current_handler,
                "callback",
                None
            )

            callback_name = getattr(
                callback,
                "__name__",
                ""
            )

            if callback_name in GENERIC_CALLBACK_NAMES:
                continue

            try:

                check_result = current_handler.check_update(
                    fake_update
                )

            except Exception as e:

                print(
                    f"⚠️ تعذر فحص Handler {callback_name}: {e}"
                )

                continue

            if not check_result:
                continue

            try:

                current_handler.collect_additional_context(
                    context,
                    fake_update,
                    application,
                    check_result
                )

                await current_handler.handle_update(
                    fake_update,
                    application,
                    check_result,
                    context
                )

                # نحفظ الـhandler نفسه
                _resolved_handlers_cache[text] = (
                    current_handler
                )

                return True

            except Exception as e:

                print(
                    f"❌ خطأ أثناء تشغيل الأمر {old_command}: {e}"
                )

                return False

    return False
