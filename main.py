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

from games.big_game_join import (
    join_big_game_router,
    leave_big_game_router,
    begin_big_game_router,
    continue_big_game_router,
    end_big_game_router,
)

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
    leave_image_quiz,
    add_image_quiz_player,
    image_quiz_settings,
    begin_image_quiz,
    continue_image_quiz,
    end_image_quiz,
    check_image_quiz_message,
    image_quiz_callback,
    add_manual_image_command,
    receive_manual_image,
    cancel_manual_image,
    delete_manual_image_command,
    receive_delete_manual_image,
    cancel_delete_manual_image,
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
    warning_command,
    clear_warnings_command,
    reveal_restrictions_command,
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
from handlers.developer_panel import (
    create_developer_panel_tables,
    developer_panel_command,
    developer_panel_callback,
    developer_panel_message,
    track_private_start,
    track_bot_chat_member,
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
    change_rank,
    create_group_ranks_table,
    dev_list_command,
    rank_list_command,
    clear_dev_command,
    clear_rank_command,
    clear_all_ranks_command,
    roles_clear_callback,
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


from button_colors import (
    patch_inline_keyboard_buttons,
    register_existing_panel_buttons
)
from handlers.button_colors import (
    change_button_color_start,
    change_button_color_handler
)
from handlers.send import (
    send_command,
    delete_slash_command,
    handle_send_media,
)
from handlers.repetition import (
    create_repetition_tables,
    repetition_message_handler,
    repetition_expiry_loop,
    enable_repetition,
    disable_repetition,
    set_repetition_start,
    receive_repetition_duration,
    set_mute_duration,
    set_restrict_duration,
    set_repetition_rank,
    clear_user_repetition_warnings,
    repetition_action_callback,
)
from handlers.blocked_words import (
    ensure_blocked_words_tables,
    blocked_words_message_handler,
    blocked_words_callback,
    blocked_words_expiry_loop,
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

from handlers.tasliyat import (
    create_bank_account,
    bank_callback,
    my_bank_account,
    delete_bank_account,
    salary,
    tip,
    store,
    my_possessions,
    other_possessions,
    buy_sell,
    gift,
    rob,
    transfer,
    transfer_account_number,
    transfer_message_callback,
    transfer_message_receiver,
    invest,
    luck,
    show_scratch_codes,
    scratch_code,
    reset_scratch_cooldown,
    flush_pending_tasliyat_cooldowns,
)

from games.xo import (
    start_xo_game,
    xo_callback,
)

from games.rock_paper_scissors import (
    start_rock_paper_scissors,
    rock_paper_scissors_callback,
)


from handlers.mandatory_subscription import (
    ensure_mandatory_subscription_tables,
    mandatory_subscription_guard,
    mandatory_subscription_commands,
)

from games.demon_nawaf import (
    ensure_demon_tables,
    start_demon_nawaf,
    demon_nawaf_callback,
    demon_nawaf_private_start,
)

from handlers.emoji_reactions import (
    ensure_emoji_reactions_table,
    emoji_reactions_handler,
)

from ai_assistant import ensure_ai_tables, ai_assistant_message

from handlers.youtube_audio import (
    youtube_audio_search,
    youtube_audio_callback,
)

from handlers.music import (
    music_message_handler,
    music_callback,
    voice_chat_started,
    voice_chat_ended,
)

from music_call import (
    start_music_call,
    shutdown_music_call,
)

from handlers.temporary_messages import (
    ensure_temporary_message_tables,
    temporary_message_command,
    temporary_message_pending_handler,
    temporary_message_callback,
    temporary_message_scheduler,
    track_temporary_message_chat,
)

from account_clock import start_account_clock, shutdown_account_clock

from auto_private_reply import (
    start_auto_private_reply,
    shutdown_auto_private_reply,
)

from name_reaction import (
    start_name_reaction,
    shutdown_name_reaction
)

# ==================================================
# نظام الألعاب الجديد
# ==================================================
from games.engine import (
    ensure_game_tables,
    game_message_handler,
)

from handlers.registration import register_all_handlers

import os
import asyncio
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import unquote
# ==================================================
# 👑 المطور
# ==================================================
OWNER_ID = 8453977662
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
    print("==========================================")
    print(
        f"🚀 Mini App running on port {port}"
    )
    print("==========================================")
    handler = MiniAppHandler
    server = HTTPServer(
        (
            "0.0.0.0",
            port
        ),
        handler
    )
    server.serve_forever()
# ==================================================
# استخراج ID الصورة - الخاص فقط
# ==================================================
async def get_photo_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.effective_user:
        return
    if update.effective_user.id != OWNER_ID:
        return
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
    create_developer_panel_tables()
    ensure_demon_tables()
    ensure_game_tables()
    ensure_temporary_message_tables()
    ensure_emoji_reactions_table()
    ensure_ai_tables()
    ensure_blocked_words_tables()
    ensure_mandatory_subscription_tables()
    create_group_ranks_table()
    create_repetition_tables()
    create_profile_reply_tables()
    patch_inline_keyboard_buttons()
    register_existing_panel_buttons()
    # ==================================================
    # مهام الخلفية
    # ==================================================
    message_flush_task = None
    moderation_expiry_task = None
    blocked_words_expiry_task = None
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
        global blocked_words_expiry_task

        message_flush_task = asyncio.create_task(
            automatic_message_flush()
        )

        moderation_expiry_task = asyncio.create_task(
            moderation_expiry_loop(application)
        )

        blocked_words_expiry_task = asyncio.create_task(
            blocked_words_expiry_loop(application)
        )

        application.create_task(
            repetition_expiry_loop(application)
        )

        application.create_task(
            temporary_message_scheduler(application)
        )

        # ==========================================
        # تشغيل حساب الموسيقى والميزات المرتبطة به
        # ==========================================


        try:
            music_started = await start_music_call()

            if music_started:
                await start_account_clock()
                await start_auto_private_reply()
                await start_name_reaction()

        except Exception as e:
            print(f"⚠️ تعذر تشغيل حساب الصوت: {e}")


    async def post_shutdown(application):
        global message_flush_task
        global moderation_expiry_task
        global blocked_words_expiry_task

        # إيقاف الساعة أولاً
        try:
            await shutdown_account_clock()
        except Exception as e:
            print(f"⚠️ تعذر إيقاف الساعة: {e}")

        # إيقاف حفظ الرسائل
        if message_flush_task:
            message_flush_task.cancel()
            try:
                await message_flush_task
            except asyncio.CancelledError:
                pass

        # إيقاف انتهاء القيود
        if moderation_expiry_task:
            moderation_expiry_task.cancel()
            try:
                await moderation_expiry_task
            except asyncio.CancelledError:
                pass

        # إيقاف انتهاء الكلمات المحظورة
        if blocked_words_expiry_task:
            blocked_words_expiry_task.cancel()
            try:
                await blocked_words_expiry_task
            except asyncio.CancelledError:
                pass


        # إيقاف الساعة
        try:
            await shutdown_account_clock()
        except Exception as e:
            print(f"⚠️ تعذر إيقاف الساعة: {e}")

        # إيقاف الرد التلقائي
        try:
            await shutdown_auto_private_reply()
        except Exception as e:
            print(f"⚠️ تعذر إيقاف الرد التلقائي: {e}")

        # إيقاف حساب الموسيقى
        try:
            await shutdown_music_call()
        except Exception as e:
            print(f"⚠️ تعذر إيقاف حساب الموسيقى: {e}")
        # إيقاف حساب الموسيقى
        try:
            await shutdown_name_reaction()
        except Exception as e:
            print(f"⚠️ تعذر إيقاف تفاعل نواف: {e}")

        try:
            await shutdown_music_call()
        except Exception as e:
            print(f"⚠️ تعذر إيقاف حساب الموسيقى: {e}")
        # حفظ الرسائل المعلقة
        try:
            await flush_user_messages()
            print("💾 تم حفظ الرسائل المعلقة قبل إيقاف البوت")
        except Exception as e:
            print(f"⚠️ تعذر حفظ الرسائل عند الإيقاف: {e}")

        # حفظ النقاط المعلقة
        try:
            await flush_pending_points()
            print("💰 تم حفظ النقاط المعلقة قبل إيقاف البوت")
        except Exception as e:
            print(f"⚠️ تعذر حفظ النقاط عند الإيقاف: {e}")

        # حفظ أوقات التسليات المعلقة
        try:
            await flush_pending_tasliyat_cooldowns()
            print("⏱️ تم حفظ أوقات التسليات المعلقة قبل إيقاف البوت")
        except Exception as e:
            print(f"⚠️ تعذر حفظ أوقات التسليات عند الإيقاف: {e}")

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

    # تسجيل جميع المعالجات من النظام الموحد
    register_all_handlers(app)

    
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
