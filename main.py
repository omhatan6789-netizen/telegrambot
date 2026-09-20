from telegram import Update

from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)

from config import BOT_TOKEN
from permissions import permission_command
from database import create_tables

from games.hide_and_seek import (
    start_hide_game,
    join_hide_game,
    begin_hide_game,
    end_hide_game,
    hide_number_callback,
    search_number_callback
)

from handlers.games_help import games_help

from games.penalties import (
    start_penalty_game,
    join_penalty_game,
    distribute_penalties,
    distribution_callback,
    manual_team_command,
    begin_penalties,
    penalty_direction_callback,
    continue_penalties,
    end_penalty_game,
)


from handlers.delete_messages import delete_messages

from games.big_game_join import join_big_game_router

from games.word_race import (
    start_word_race,
    join_word_race,
    leave_word_race,
    word_race_mode,
    word_race_distribution,
    word_race_manual_team,
    word_race_add_solo,
    begin_word_race,
    check_word_race_message,
    word_race_callback,
    continue_word_race,
    end_word_race,
    WordRaceActiveFilter,
)

# ==================================================
# 🖼️ توقع الصورة
# ==================================================

from games.image_quiz.image_quiz import (
    start_image_quiz,
    join_image_quiz,
    leave_image_quiz,
    add_image_quiz_player,
    image_quiz_settings,
    begin_image_quiz,
    continue_image_quiz,
    end_image_quiz,
    check_image_quiz_message,
    image_quiz_callback,
)

from games.liars_table import (
    start_liars_table,
    join_liars_table,
    leave_liars_table,
    begin_liars_table,
    end_liars_table,
    liars_table_callback,
    liars_table_private_start,
)

from handlers.games_menu import (
    games_menu_command,
    games_menu_callback,
)


from games.liar import (
    start_liar_game_lobby,
    join_liar_game,
    leave_liar_game,
    begin_liar_game,
    force_voting,
    end_liar_game,
    liar_lobby_callback,
    liar_vote_callback,
    liar_guess_callback,
    check_liar_message,
)

# ==================================================
# الأنمي
# ==================================================

from games.anime_game import (
    start_anime_quiz,
    check_anime_answer
)


# ==================================================
# البداية
# ==================================================

from handlers.start import start


from handlers.commands_menu import (
    commands_menu_start,
    commands_menu_callback
)


# ==================================================
# قفل الأوامر
# ==================================================

from handlers.command_lock import (
    lock_command,
    save_lock_rank,
    open_command
)


# ==================================================
# حارس الأوامر
# ==================================================

from handlers.command_guard import command_guard


# ==================================================
# الأوامر المضافة
# ==================================================

from custom_commands import (
    add_command_start,
    receive_old_command,
    receive_new_command,
    custom_commands_list,
    delete_command_start,
    delete_command,
    delete_all_commands,
    check_custom_commands,
    WAIT_OLD,
    WAIT_NEW
)


from handlers.moderation import (
    moderation_command,
    check_muted_message,

    unmute_command,
    unrestrict_command,
    unban_command,
    clear_restrictions_command,

    moderation_lists_command,
    clear_list_callback,

    enable_durations_command,
    disable_durations_command,
    enable_reasons_command,
    disable_reasons_command,


    moderation_expiry_loop,
    reveal_command,
)

# ==================================================
# الملفات الشخصية وردود الادمن
# ==================================================

from handlers.profile_replies import (
    create_profile_reply_tables,

    developer_command,
    change_developer_username,

    owner_command,
    change_owner_username,

    add_my_admin_reply,
    delete_my_admin_reply,
    delete_other_admin_reply,

    admin_replies_list,
    enable_admin_replies,
    disable_admin_replies,
    delete_all_admin_replies_command,

    check_admin_profile_reply,
    profile_reply_pending_handler,
)



# ==================================================
# النقاط
# ==================================================

from handlers.points import (
    my_points,
    top_points,
    add_points_command,
    remove_points_command,
    sell_points,
    flush_pending_points
)


# ==================================================
# المستخدمين
# ==================================================

from handlers.users import (
    user_id_command,
    save_join_date,
    save_user_message,
    flush_user_messages
)


# ==================================================
# الرتب
# ==================================================

from handlers.roles import (
    roles_command,
    change_rank
)


from handlers.start_editor import (
    start_editor_command,
    start_editor_callback,
    start_editor_special_callback,
    start_editor_message,
)

# ==================================================
# الردود
# ==================================================

from handlers.replies import (
    add_reply_start,
    add_reply_handler,
    check_replies,
    replies_list,

    add_special_reply_start,
    add_special_reply_handler,
    special_replies_list,

    edit_special_reply_start,
    edit_special_reply_handler,

    edit_reply_start,
    edit_reply_handler,

    delete_special_reply_start,
    delete_special_reply_handler,

    delete_reply_start,
    delete_reply_handler,

    delete_all_replies,
    delete_all_special_replies
)

  
# ==================================================
# أسرع كلمة
# ==================================================

from games.speed_words import (
    start_speed_words,
    check_speed_words
)


# ==================================================
# الألعاب
# ==================================================

from games.games_manager import (
    add_game_start,
    add_game_handler,

    games_list,
    delete_game,
    enable_game,
    disable_game,
    enable_all_games,
    disable_all_games,

    add_question_start,
    add_question_handler,

    questions_list,
    delete_question,

    play_game,
    check_game_answer
)

from button_colors import (
    patch_inline_keyboard_buttons,
    register_existing_panel_buttons
)

from handlers.button_colors import (
    change_button_color_start,
    change_button_color_handler
)

# ==================================================
# الهمسات
# ==================================================

from handlers.whisper import (
    whisper_command,
    whisper_start,
    whisper_private_message,
    whisper_callbacks,
    enable_whispers_command,
    disable_whispers_command,
    whispers_list_command,
)

import os
import asyncio
import threading

from http.server import SimpleHTTPRequestHandler, HTTPServer
from functools import partial
from urllib.parse import unquote

# =========================================================
# 🌐 Mini App Web Server
# =========================================================
class MiniAppHandler(SimpleHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/health":

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )

            self.end_headers()

            self.wfile.write(
                b"Bot is running"
            )

            return

        if self.path == "/":

            self.path = "/index.html"

        return super().do_GET()

    def translate_path(self, path):

        path = path.split("?", 1)[0]

        path = unquote(path)

        path = path.lstrip("/")

        # ==========================================
        # 🖼️ صور Mini App
        # ==========================================

        if path.startswith("images/"):

            image_name = path[len("images/"):]

            return os.path.join(
                self.base_path,
                "mini_app",
                "images",
                image_name
            )

        # ==========================================
        # 📄 ملفات Mini App
        # ==========================================

        return os.path.join(
            self.base_path,
            "mini_app",
            path
        )

    def log_message(self, format, *args):
        return


# ==================================================
# 🌐 تشغيل سيرفر Mini App
# ==================================================

def start_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    base_path = os.path.dirname(
        os.path.abspath(__file__)
    )

    # ==========================================
    # 📁 المسار الأساسي
    # ==========================================

    MiniAppHandler.base_path = base_path

    mini_app_path = os.path.join(
        base_path,
        "mini_app"
    )

    images_path = os.path.join(
        base_path,
        "mini_app",
        "images"
    )

    # ==========================================
    # 🌐 معلومات Mini App
    # ==========================================

    print("==========================================")
    print("🌐 Mini App Server")
    print("==========================================")

    print(
        "📁 Mini App path:",
        mini_app_path
    )

    print(
        "📄 index.html:",
        os.path.isfile(
            os.path.join(
                mini_app_path,
                "index.html"
            )
        )
    )

    print(
        "🎨 style.css:",
        os.path.isfile(
            os.path.join(
                mini_app_path,
                "style.css"
            )
        )
    )

    print(
        "⚙️ app.js:",
        os.path.isfile(
            os.path.join(
                mini_app_path,
                "app.js"
            )
        )
    )

    # ==========================================
    # 🖼️ مجلد الصور
    # ==========================================

    print(
        "🖼️ images folder:",
        os.path.isdir(images_path)
    )

    for filename in [
        "bot.JPG",
        "background.JPG",
        "group.JPG",
        "channel.JPG",
        "developer.JPG"
    ]:

        print(
            f"🖼️ {filename}:",
            os.path.isfile(
                os.path.join(
                    images_path,
                    filename
                )
            )
        )

    # ==========================================
    # 🚀 تشغيل السيرفر
    # ==========================================

    handler = MiniAppHandler

    server = HTTPServer(
        (
            "0.0.0.0",
            port
        ),
        handler
    )

    print("==========================================")

    print(
        f"🚀 Mini App running on port {port}"
    )

    print("==========================================")

    server.serve_forever()
# ==================================================
# استخراج ID الصورة - الخاص فقط
# ==================================================

async def get_photo_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.photo:
        return

    photo = update.message.photo[-1]

    await update.message.reply_text(
        f"🆔 ID الصورة:\n\n`{photo.file_id}`",
        parse_mode="Markdown"
    )


# ==================================================
# عرض صورة عن طريق ID - الخاص فقط
# ==================================================

WAIT_PHOTO_ID = 999


async def show_photo_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "• أرسل ID الصورة"
    )

    return WAIT_PHOTO_ID


async def show_photo_by_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message or not update.message.text:
        return WAIT_PHOTO_ID

    photo_id = update.message.text.strip()

    try:
        await update.message.reply_photo(
            photo=photo_id
        )

        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(
            "• الـID غير صحيح أو الصورة غير متاحة."
        )

        return WAIT_PHOTO_ID

# ==================================================
# MAIN
# ==================================================

def main():

    # ==================================================
    # إنشاء الجداول
    # ==================================================

    create_tables()
    create_profile_reply_tables()
    patch_inline_keyboard_buttons()
    register_existing_panel_buttons()

    # ==================================================
    # إنشاء التطبيق
    # ==================================================

    # ==================================================
    # الحفظ التلقائي لرسائل المستخدمين
    # ==================================================

    message_flush_task = None
    moderation_expiry_task = None


    async def automatic_message_flush():

        while True:

            try:
                await flush_user_messages()

            except asyncio.CancelledError:
                break

            except Exception as e:
                print(
                    f"⚠️ خطأ في الحفظ التلقائي للرسائل: {e}"
                )

            await asyncio.sleep(5)


    async def post_init(application):

        global message_flush_task
        global moderation_expiry_task

        message_flush_task = asyncio.create_task(
            automatic_message_flush()
        )

        moderation_expiry_task = asyncio.create_task(
            moderation_expiry_loop(application)
        )


    async def post_shutdown(application):

        global message_flush_task
        global moderation_expiry_task

        if message_flush_task:

            message_flush_task.cancel()

            try:
                await message_flush_task
            except asyncio.CancelledError:
                pass

        if moderation_expiry_task:

            moderation_expiry_task.cancel()

            try:
                await moderation_expiry_task
            except asyncio.CancelledError:
                pass

        try:
            await flush_user_messages()

            print(
                "💾 تم حفظ الرسائل المعلقة قبل إيقاف البوت"
            )

        except Exception as e:

            print(
                f"⚠️ تعذر حفظ الرسائل عند الإيقاف: {e}"
            )

        try:
            await flush_pending_points()

            print(
                "💰 تم حفظ النقاط المعلقة قبل إيقاف البوت"
            )

        except Exception as e:

            print(
                f"⚠️ تعذر حفظ النقاط عند الإيقاف: {e}"
            )


    # ==================================================
    # إنشاء التطبيق
    # ==================================================

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    
    # ==================================================
    # الأوامر المضافة
    # ==================================================

    add_command_conv = ConversationHandler(

        entry_points=[
            MessageHandler(
                filters.Regex(r"^اضف امر$"),
                add_command_start
            )
        ],

        states={

            WAIT_OLD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_old_command
                )
            ],

            WAIT_NEW: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_new_command
                )
            ]

        },

        fallbacks=[]

    )    
    app.add_handler(
        add_command_conv,
        group=-2
    )


    # قائمة الأوامر المضافة

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الاوامر المضافة$"),
            custom_commands_list
        )
    )


    # بدء حذف أمر

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح امر$"),
            delete_command_start
        )
    )


    # استقبال اسم الأمر المراد حذفه

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_command
        ),
        group=-2
    )


    # حذف جميع الأوامر

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح الاوامر المضافة$"),
            delete_all_commands
        )
    )


    # ==================================================
    # منع / سماح
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(منع|سماح)(?:\s+.+)?$"
            ),
            permission_command
        ),
        group=-10
    )

    
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.Regex(r"^(تعديل ستارت|الستارت)$"),
            start_editor_command
        ),
        group=-8
    )

    app.add_handler(
        CallbackQueryHandler(
            start_editor_callback,
            pattern=r"^startedit:(?:menu|message|buttons|add_button|order_button|delete_button|access|image)$"
        ),
        group=-7
    )

    app.add_handler(
        CallbackQueryHandler(
            start_editor_special_callback,
            pattern=r"^startedit:(?:access_add|access_delete|image_add|image_delete|image_delete_all)$"
        ),
        group=-7
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            start_editor_message
        ),
        group=-8
    )
    
    # ==================================================
    # حارس الأوامر
    # ==================================================

    # ==================================================
    # الأوامر المضافة وتشغيلها
    # ==================================================

    async def custom_command_alias_handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        executed = await check_custom_commands(
            update,
            context,
            application=app
        )

        if executed:
            raise ApplicationHandlerStop()


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            custom_command_alias_handler
        ),
        group=-7
    )
    
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            command_guard
        ),
        group=-5
    )   

    print("🔥 تسجيل check_muted_message الآن")
    print("📌 function:", check_muted_message)
    
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS,
            check_muted_message
        ),
        group=-30
    )

    print("✅ check_muted_message تم تسجيلها")   

    # --------------------------------------------------
    # تفعيل المدة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^تفعيل المدة للمشرفين$"
            ),
            enable_durations_command
        ),
        group=-20
    )

    # --------------------------------------------------
    # تعطيل المدة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^تعطيل المدة للمشرفين$"
            ),
            disable_durations_command
        ),
        group=-20
    )

    # --------------------------------------------------
    # تفعيل الأسباب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^تفعيل الاسباب$"
            ),
            enable_reasons_command
        ),
        group=-20
    )
    

    # --------------------------------------------------
    # تعطيل الأسباب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^تعطيل الاسباب$"
            ),
            disable_reasons_command
        ),
        group=-20
    )

    # --------------------------------------------------
    # كشف
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^كشف(?:\s+@[A-Za-z0-9_]+|\s+\d+)?$"
            ),
            reveal_command
        ),
        group=-19
    )

    # --------------------------------------------------
    # كتم / تقييد / حظر
    #
    # يسمح بوجود مدة وهدف وسبب.
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^(كتم|تقييد|حظر)(?:\s+.+)?$"
            ),
            moderation_command
        ),
        group=-18
    )

    # --------------------------------------------------
    # إلغاء الكتم
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^الغاء الكتم(?:\s+.+)?$"
            ),
            unmute_command
        ),
        group=-18
    )

    # --------------------------------------------------
    # إلغاء التقييد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^الغاء التقييد(?:\s+.+)?$"
            ),
            unrestrict_command
        ),
        group=-18
    )

    # --------------------------------------------------
    # إلغاء الحظر
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^الغاء الحظر(?:\s+.+)?$"
            ),
            unban_command
        ),
        group=-18
    )

    # --------------------------------------------------
    # رفع القيود
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^رفع القيود(?:\s+.+)?$"
            ),
            clear_restrictions_command
        ),
        group=-18
    )

    # --------------------------------------------------
    # القوائم
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^(المكتومين|المقيدين|المحظورين)$"
            ),
            moderation_lists_command
        ),
        group=-18
    )

    # --------------------------------------------------
    # أزرار مسح القوائم
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            clear_list_callback,
            pattern=r"^moderation:clear:"
        ),
        group=-18
    )
    # ==================================================
    # قفل وفتح الأوامر
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^قفل امر .+$"),
            lock_command
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^فتح امر .+$"),
            open_command
        ),
        group=0
    )


    # --------------------------------------------------
    # حفظ الرتبة التي اختارها المستخدم لقفل الأمر
    #
    # هذا كان ناقصًا عندك
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_lock_rank
        ),
        group=1
    )


    # ==================================================
    # الهمسات - /start
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^/start\s+whisper_[A-Za-z0-9_-]+$"),
            whisper_start,
        )
    )


    # ==================================================
    # START
    # ==================================================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )
    
    # ==================================================
    # 📋 Mini App - أوامر البوت
    # /start commands
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.Regex(r"^/start(?:@\w+)?\s+commands$"),
            commands_menu_start
        ),
        group=-5
    )


    # ==================================================
    # 📋 قائمة أوامر البوت
    # ==================================================

    # /help
    app.add_handler(
        CommandHandler(
            "help",
            commands_menu_start
        ),
        group=-5
    )

    # الأوامر / الاوامر
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(?:الأوامر|الاوامر)$"),
            commands_menu_start
        ),
        group=-8
    )
    # ==================================================
    # المستخدم
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^ايدي$"),
            user_id_command
        )
    )


    # ==================================================
    # رتبتي / رتبته
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(رتبتي|رتبته(?:\s+@[A-Za-z0-9_]+|\s+\d+)?)$"
            ),
            roles_command
        )
    )


    # ==================================================
    # الملفات الشخصية وردود الادمن
    # ==================================================

    # --------------------------------------------------
    # انتظار البيانات المؤقتة
    # لازم يكون قبل المعالجات العامة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            profile_reply_pending_handler
        ),
        group=-11
    )
    # --------------------------------------------------
    # المطور
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^المطور$"),
            developer_command
        ),
        group=0
    )

    # --------------------------------------------------
    # تغيير يوزر المطور
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تغيير يوزر المطور$"),
            change_developer_username
        ),
        group=0
    )

    # --------------------------------------------------
    # المالك
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^المالك$"),
            owner_command
        ),
        group=0
    )

    # --------------------------------------------------
    # تغيير يوزر المالك
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تغيير يوزر المالك$"),
            change_owner_username
        ),
        group=0
    )

    # --------------------------------------------------
    # إضافة ردي
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف ردي$"),
            add_my_admin_reply
        ),
        group=0
    )

    # --------------------------------------------------
    # حذف ردي
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف ردي$"),
            delete_my_admin_reply
        ),
        group=0
    )

    # --------------------------------------------------
    # حذف رده
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف رده$"),
            delete_other_admin_reply
        ),
        group=0
    )

    # --------------------------------------------------
    # قائمة ردود الادمن
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^ردود الادمن$"),
            admin_replies_list
        ),
        group=0
    )

    # --------------------------------------------------
    # تفعيل ردود الادمن
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تفعيل ردود الادمن$"),
            enable_admin_replies
        ),
        group=0
    )

    # --------------------------------------------------
    # تعطيل ردود الادمن
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعطيل ردود الادمن$"),
            disable_admin_replies
        ),
        group=0
    )

    # --------------------------------------------------
    # حذف جميع ردود الادمن
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف ردود الادمن$"),
            delete_all_admin_replies_command
        ),
        group=0
    )

    # --------------------------------------------------
    # تشغيل ردود الادمن
    # بعد أوامر النظام وقبل الردود العادية
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            check_admin_profile_reply
        ),
        group=39
    )
    # ==================================================
    # كشف المجموعة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كشف المجموعة$"
            ),
            roles_command
        )
    )



    # ==================================================
    # رفع / تنزيل الرتب
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(رفع|تنزيل) "
                r"(Dev|المالك|نائب المالك|ادمن اساسي|ادمن|مميز)"
                r"(?:\s+(@[A-Za-z0-9_]+|\d+))?$"
            ),
            change_rank
        )
    )

    # ==================================================
    # الردود المميزة
    # ==================================================

    # بدء إضافة رد مميز

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف رد مميز$"),
            add_special_reply_start
        ),
        group=0
    )


    # استقبال خطوات إضافة الرد المميز

    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_special_reply_handler
        ),
        group=2
    )


    # --------------------------------------------------
    # تعديل رد مميز
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعديل رد مميز$"),
            edit_special_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            edit_special_reply_handler
        ),
        group=3
    )


    # --------------------------------------------------
    # حذف رد مميز
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح رد مميز$"),
            delete_special_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            delete_special_reply_handler
        ),
        group=4
    )


    # --------------------------------------------------
    # قائمة الردود المميزة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الردود المميزة$"),
            special_replies_list
        )
    )


    # ==================================================
    # الردود العادية
    # ==================================================

    # --------------------------------------------------
    # إضافة رد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف رد$"),
            add_reply_start
        ),
        group=-6
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_reply_handler
        ),
        group=5
    )


    # --------------------------------------------------
    # تعديل رد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعديل رد$"),
            edit_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            edit_reply_handler
        ),
        group=6
    )


    # --------------------------------------------------
    # حذف رد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح رد$"),
            delete_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            delete_reply_handler
        ),
        group=7
    )


    # --------------------------------------------------
    # قائمة الردود
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الردود$"),
            replies_list
        )
    )


    # --------------------------------------------------
    # حذف جميع الردود
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح الردود$"),
            delete_all_replies
        )
    )


    # --------------------------------------------------
    # حذف جميع الردود المميزة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح الردود المميزة$"),
            delete_all_special_replies
        )
    )


    # ==================================================
    # النقاط
    # ==================================================
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف \d+$"),
            add_points_command
        ),
        group=-1
    )

    
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^خصم \d+$"),
            remove_points_command
        ),
        group=-1
    )

    
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^بيع نقاطي \d+$"),
            sell_points
        ),
        group=-1
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^نقاطي$"),
            my_points
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^توب$"),
            top_points
        )
    )
    


    # ==================================================
    # الهمسات - أوامر القروب
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(همسه|همسة|اهمس)$"),
            whisper_command,
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تفعيل الهمسات$"),
            enable_whispers_command,
        ),
        group=0,
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعطيل الهمسات$"),
            disable_whispers_command,
        ),
        group=0,
    )

    # ==================================================
    # الهمسات - استقبال الهمسة في الخاص
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE,
            whisper_private_message,
        ),
        group=0,
    )

    # ==================================================
    # الهمسات - أمر المطور
    # ==================================================

    # ==================================================
    # الهمسات - أمر المطور
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الهمسات$"),
            whispers_list_command,
        ),
        group=-1,
    )


    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.Regex(r"^\.لعبة$"),
            games_menu_command,
        ),
        group=-4,
    )
    # ==================================================
    # 🐎 سباق الكلمات
    # ==================================================

    # بدء سباق الكلمات
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^سباق الكلمات$"),
            start_word_race
        ),
        group=-4
    )

    # خروج
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^خروج$"]),
            leave_word_race
        ),
        group=-4
    )

    # .الطور
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^\.الطور$"]),
            word_race_mode
        ),
        group=-4
    )

    # .توزيع
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^\.وزع$"]),
            word_race_distribution
        ),
        group=-4
    )

    # .اضافة احمر / ازرق / اخضر / اصفر
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter(
                [r"^\.اضافة (احمر|ازرق|اخضر|اصفر)$"]
            ),
            word_race_manual_team
        ),
        group=-4
    )

    # .ابدا
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^\.ابدا$"]),
            begin_word_race
        ),
        group=-4
    )

    # .كمل
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^\.كمل$"]),
            continue_word_race
        ),
        group=-4
    )

    # إنهاء سباق الكلمات
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter(
                [r"^انهاء سباق الكلمات$"]
            ),
            end_word_race
        ),
        group=-4
    )

    # أزرار سباق الكلمات
    app.add_handler(
        CallbackQueryHandler(
            word_race_callback,
            pattern=r"^wr:"
        ),
        group=-4
    )

    # إجابات سباق الكلمات
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            check_word_race_message
        ),
        group=9
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            check_word_race_message
        ),
        group=9
    )

    # ==================================================
    # أسرع كلمة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^كلمات$"),
            start_speed_words
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_speed_words
        ),
        group=10
    )


    # ==================================================
    # الألعاب
    # ==================================================

    # ==================================================
    # تعديل لون زر
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^تعديل لون$"),
            change_button_color_start
        ),
        group=-20
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            change_button_color_handler
        ),
        group=-19
    )

    # ==================================================
    # أدوات الصور - الخاص فقط
    # ==================================================

    show_photo_conv = ConversationHandler(

        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^اعرض الصورة$"),
                show_photo_start
            )
        ],

        states={
            WAIT_PHOTO_ID: [
                MessageHandler(
                    filters.ChatType.PRIVATE
                    & filters.TEXT
                    & ~filters.COMMAND,
                    show_photo_by_id
                )
            ]
        },

        fallbacks=[],    
            
        allow_reentry=True
    )

    app.add_handler(
        show_photo_conv,
        group=-21
    )


    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.PHOTO,
            get_photo_id
        ),
        group=-20
    )

    # --------------------------------------------------
    # إضافة لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف لعبة$"),
            add_game_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_game_handler
        ),
        group=21
    )


    # --------------------------------------------------
    # قائمة الألعاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الالعاب$"),
            games_list
        )
    )


    # ==================================================
    # الأسئلة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف سؤال(?:\s|$)"),
            add_question_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            (
                filters.TEXT |
                filters.PHOTO
            ) & ~filters.COMMAND,
            add_question_handler
        ),
        group=23
    )


    # --------------------------------------------------
    # قائمة الأسئلة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اسئلة"),
            questions_list
        )
    )


    # --------------------------------------------------
    # حذف سؤال
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف سؤال"),
            delete_question
        )
    )


    # --------------------------------------------------
    # حذف لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف لعبة"),
            delete_game
        )
    )


    # --------------------------------------------------
    # تفعيل لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تفعيل لعبة"),
            enable_game
        )
    )


    # --------------------------------------------------
    # تعطيل لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعطيل لعبة"),
            disable_game
        )
    )


    # --------------------------------------------------
    # تفعيل جميع الألعاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تفعيل الالعاب$"),
            enable_all_games
        )
    )


    # --------------------------------------------------
    # تعطيل جميع الألعاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعطيل الالعاب$"),
            disable_all_games
        )
    )


    # ==================================================
    # لعبة الأنمي
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^انمي$"),
            start_anime_quiz
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_anime_answer
        ),
        group=32
    )


    # ==================================================
    # الألعاب المخصصة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            play_game
        ),
        group=30
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_game_answer
        ),
        group=31
    )



    # ==================================================
    # تشغيل الردود
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_replies
        ),
        group=40
    )


    # ==================================================
    # المستخدمين
    # ==================================================

    app.add_handler(
        ChatMemberHandler(
            save_join_date,
            ChatMemberHandler.CHAT_MEMBER
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_user_message
        ),
        group=50
    )



    # ==================================================
    # 🖼️ توقع الصورة
    # ==================================================

    # --------------------------------------------------
    # بدء لعبة توقع الصورة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^توقع الصورة$"),
            start_image_quiz
        ),
        group=-6
    )

    # --------------------------------------------------
    # دخول توقع الصورة
    #
    # لازم يكون قبل join_big_game_router
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^دخول$"),
            join_image_quiz
        ),
        group=-6
    )

    # --------------------------------------------------
    # خروج توقع الصورة
    #
    # يعمل قبل وبعد بدء القيم
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^خروج$"),
            leave_image_quiz
        ),
        group=-6
    )

    # --------------------------------------------------
    # .اضافة
    #
    # يستخدم بالرد على رسالة الشخص
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.اضافة$"),
            add_image_quiz_player
        ),
        group=-6
    )

    # --------------------------------------------------
    # .اعدادات
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.اعدادات$"),
            image_quiz_settings
        ),
        group=-6
    )

    # --------------------------------------------------
    # .ابدا
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.ابدا$"),
            begin_image_quiz
        ),
        group=-6
    )

    # --------------------------------------------------
    # .كمل
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.كمل$"),
            continue_image_quiz
        ),
        group=-6
    )

    # --------------------------------------------------
    # .انهاء
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.انهاء$"),
            end_image_quiz
        ),
        group=-6
    )

    # --------------------------------------------------
    # أزرار إعدادات توقع الصورة
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            image_quiz_callback,
            pattern=r"^iq:"
        ),
        group=-6
    )

    # --------------------------------------------------
    # إجابات توقع الصورة
    #
    # لازم تكون قبل معالجات إجابات الألعاب الأخرى
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            check_image_quiz_message
        ),
        group=8
    )
    # ==================================================
    # 🍻 طاولة الكذب
    # ==================================================

    # --------------------------------------------------
    # بدء طاولة الكذب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^طاولة الكذب$"),
            start_liars_table
        ),
        group=-4
    )


    # --------------------------------------------------
    # دخول طاولة الكذب
    # يتم عبر big_game_join_router
    # لكن يجب أن يكون قبل الهاندلرات القديمة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^دخول$"),
            join_big_game_router
        ),
        group=-4
    )


    # --------------------------------------------------
    # خروج من طاولة الكذب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.خروج$"),
            leave_liars_table
        ),
        group=-4
    )


    # --------------------------------------------------
    # بدء طاولة الكذب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.ابدا$"),
            begin_liars_table
        ),
        group=-4
    )


    # --------------------------------------------------
    # إنهاء طاولة الكذب
    # للأدمن والمالك
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^انهاء طاولة الكذب$"),
            end_liars_table
        ),
        group=-4
    )


    # --------------------------------------------------
    # أزرار طاولة الكذب
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            liars_table_callback,
            pattern=r"^lt:"
        ),
        group=-4
    )


    # --------------------------------------------------
    # /start الخاص بطاولة الكذب
    # --------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            liars_table_private_start
        ),
        group=-4
    )

   
    # --------------------------------------------------
    # بدء لعبة الكذاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الكذاب$"),
            start_liar_game_lobby
        ),
        group=0
    )

    
    # --------------------------------------------------
    # خروج من لعبة الكذاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\.خروج$"),
            leave_liar_game
        ),
        group=-3
    )

    # --------------------------------------------------
    # بدء لعبة الكذاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\.ابدا$"),
            begin_liar_game
        ),
        group=-3
    )

    # --------------------------------------------------
    # بدء التصويت يدويًا
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\.التصويت$"),
            force_voting
        ),
        group=-3
    )

    # --------------------------------------------------
    # إنهاء لعبة الكذاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^انهاء الكذاب$"),
            end_liar_game
        ),
        group=0
    )

    # --------------------------------------------------
    # أزرار دخول / خروج الكذاب
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            liar_lobby_callback,
            pattern=r"^liar_lobby:"
        ),  
        group=-3
    )

    # --------------------------------------------------
    # أزرار التصويت
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            liar_vote_callback,
            pattern=r"^liar_vote:"
        ),
        group=-3
    )

    # --------------------------------------------------
    # أزرار تخمين الكذاب
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            liar_guess_callback,
            pattern=r"^liar_guess:"
        ),
        group=-3
    )

    # --------------------------------------------------
    # رسائل لعبة الكذاب
    # يستخدم لكشف من يكتب الكلمة السرية أثناء النقاش
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_liar_message
        ),
        group=9
    )


    # ==================================================
    # لعبة البلنتيات
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^بلنتيات$"),
            start_penalty_game
        ),  
        group=0
    )

    
    # --------------------------------------------------
    # توزيع البلنتيات
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\.وزع$"),
            distribute_penalties
        ),
        group=0
    )

    # --------------------------------------------------
    # التوزيع اليدوي
    # .احمر 1 2
    # .ازرق 1 2
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^\.(?:احمر|ازرق)(?:\s+\d+)+$"
            ),
            manual_team_command
        ),
        group=0
    )

    # --------------------------------------------------
    # بدء البلنتيات
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\.ابدا$"),
            begin_penalties
        ),
        group=0
    )

    # --------------------------------------------------
    # كمل
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\.كمل$"),
            continue_penalties
        ),
        group=0
    )

    # --------------------------------------------------
    # إنهاء البلنتيات
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^انهاء بلنتيات$"),
            end_penalty_game
        ),
        group=0
    )

    # --------------------------------------------------
    # أزرار توزيع البلنتيات
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            distribution_callback,
            pattern=r"^penalty:distribution:"
        ),
        group=-3
    )

    # --------------------------------------------------
    # أزرار اتجاه البلنتي
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            penalty_direction_callback,
            pattern=r"^penalty:direction:"
        ),
        group=-3
    )



    # ==================================================
    # لعبة الغميضة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^غميضة$"),
            start_hide_game
        ),
        group=0
    )

   
    # --------------------------------------------------
    # بدء الغميضة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^ابدا$"),
            begin_hide_game
        ),
        group=0
    )

    # --------------------------------------------------
    # إنهاء الغميضة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^انهاء غميضة$"),
            end_hide_game
        ),
        group=0
    )

    # --------------------------------------------------
    # أزرار الغميضة
    # --------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            hide_number_callback,
            pattern=r"^hide:"
        ),
        group=-3
    )

    app.add_handler(
        CallbackQueryHandler(
            search_number_callback,
            pattern=r"^search:"
        ),
        group=-3
    )




    # ==================================================
    # شرح الألعاب
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^شرح الالعاب$"),
            games_help
        )
    )

    # ==================================================
    # الهمسات - CallbackQuery
    # ==================================================

    app.add_handler(
        CallbackQueryHandler(
            whisper_callbacks,
            pattern=r"^wh_",
        )
    )


    app.add_handler(
        CallbackQueryHandler(
            games_menu_callback,
            pattern=r"^game_menu:"
        )
    )

    # ==================================================
    # 📋 أزرار قائمة الأوامر
    # ==================================================

    app.add_handler(
        CallbackQueryHandler(
            commands_menu_callback,
            pattern=r"^cmdmenu:"
        ),
        group=-4
    )
    # --------------------------------------------------
    # لوحة الأدمن
    #
    # ملاحظة:
    # هذا الـ Handler عام، لذلك لازم تكون أزرار
    # الألعاب في group=-3 حتى لا تصل إليه.
    # --------------------------------------------------


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح(?:\s*\d+)?$"),
            delete_messages
        ),
        group=-3
    )

    
    # ==================================================
    # إيقاف المعالجات بعد الفوز في الألعاب
    # ==================================================

    async def stop_after_game(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        from games.games_manager import active_games


        if not update.effective_chat:
            return


        chat_id = update.effective_chat.id


        if chat_id not in active_games:
            return


        raise ApplicationHandlerStop()


    app.add_handler(
        MessageHandler(
            filters.ALL,
            stop_after_game
        ),
        group=100
    )


    # ==================================================
    # تشغيل البوت
    # ==================================================

    print("🤖 Bot Started...")

    threading.Thread(
        target=start_web_server,
        daemon=True
    ).start()

    app.run_polling()


# ==================================================
# التشغيل
# ==================================================

if __name__ == "__main__":
    main()
