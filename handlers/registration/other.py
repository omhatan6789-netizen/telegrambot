
from telegram import Update
from telegram.ext import (
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from permissions import permission_command

from custom_commands import (
    add_command_start,
    receive_old_command,
    receive_new_command,
    custom_commands_list,
    delete_command_start,
    delete_command,
    delete_all_commands,
    check_custom_commands,
    is_alias_execution,
    WAIT_OLD,
    WAIT_NEW,
)

from handlers.send import (
    send_command,
    delete_slash_command,
    handle_send_media,
)

from handlers.developer_panel import (
    developer_panel_command,
    developer_panel_callback,
    developer_panel_message,
    track_private_start,
    track_bot_chat_member,
)

from handlers.start_editor import (
    start_editor_command,
    start_editor_callback,
    start_editor_special_callback,
    start_editor_message,
)

from handlers.command_lock import (
    lock_command,
    save_lock_rank,
    open_command,
)

from handlers.start import start

from handlers.commands_menu import (
    commands_menu_start,
    commands_menu_callback,
)

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
)

from handlers.temporary_messages import (
    temporary_message_command,
    temporary_message_pending_handler,
    temporary_message_callback,
)

from handlers.delete_messages import delete_messages

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

from ai_assistant import ai_assistant_message

from handlers.emoji_reactions import emoji_reactions_handler


def build_other_handlers(app):

    async def custom_command_alias_handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if is_alias_execution(update):
            return

        executed = await check_custom_commands(
            update,
            context,
            application=app,
        )

        if executed:
            raise ApplicationHandlerStop()

    async def temporary_message_pending_handler_safe(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if is_alias_execution(update):
            return

        await temporary_message_pending_handler(
            update,
            context,
        )

    add_command_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^اضف امر$"),
                add_command_start,
            )
        ],
        states={
            WAIT_OLD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_old_command,
                )
            ],
            WAIT_NEW: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_new_command,
                )
            ],
        },
        fallbacks=[],
    )

    return [
        # الموسيقى داخل المكالمة
        (
            1,
            -1002,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                music_message_handler,
            ),
        ),

        # البحث العادي وإرسال الصوت
        (
            2,
            -1001,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND
                & filters.Regex(r"^(?:بحث|يوت)\s+.+$"),
                youtube_audio_search,
            ),
        ),

        (
            3,
            -4,
            CallbackQueryHandler(
                youtube_audio_callback,
                pattern=r"^ytpick:",
            ),
        ),

        (
            4,
            -4,
            CallbackQueryHandler(
                music_callback,
                pattern=r"^musicpick:",
            ),
        ),

        # إشعارات المكالمة
        (
            5,
            -4,
            MessageHandler(
                filters.StatusUpdate.VIDEO_CHAT_STARTED,
                voice_chat_started,
            ),
        ),

        (
            6,
            -4,
            MessageHandler(
                filters.StatusUpdate.VIDEO_CHAT_ENDED,
                voice_chat_ended,
            ),
        ),

        # المساعد الذكي
        (
            7,
            -1000,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                ai_assistant_message,
            ),
        ),

        # التفاعلات
        (
            8,
            -1001,
            MessageHandler(
                filters.TEXT,
                emoji_reactions_handler,
            ),
        ),

        # إرسال
        (
            11,
            -30,
            MessageHandler(
                filters.Regex(
                    r"^/send(?:@[A-Za-z0-9_]+)?(?:\s+[\s\S]+)?$"
                ),
                send_command,
            ),
        ),

        (
            12,
            -29,
            MessageHandler(
                filters.ChatType.PRIVATE
                & ~filters.COMMAND,
                transfer_message_receiver,
            ),
        ),

        (
            13,
            -28,
            MessageHandler(
                filters.ChatType.PRIVATE
                & ~filters.COMMAND
                & (
                    filters.PHOTO
                    | filters.VIDEO
                    | filters.ANIMATION
                    | filters.Sticker.ALL
                    | filters.VOICE
                    | filters.AUDIO
                    | filters.Document.ALL
                ),
                handle_send_media,
            ),
        ),

        (
            14,
            -27,
            MessageHandler(
                filters.Regex(r"^/[\s\S]+$"),
                delete_slash_command,
            ),
        ),

        # الأوامر المضافة
        (
            15,
            -2,
            add_command_conv,
        ),

        (
            16,
            0,
            MessageHandler(
                filters.Regex(r"^الاوامر المضافة$"),
                custom_commands_list,
            ),
        ),

        (
            17,
            0,
            MessageHandler(
                filters.Regex(r"^مسح امر$"),
                delete_command_start,
            ),
        ),

        (
            18,
            -2,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                delete_command,
            ),
        ),

        (
            19,
            0,
            MessageHandler(
                filters.Regex(r"^مسح الاوامر المضافة$"),
                delete_all_commands,
            ),
        ),

        # منع وسماح
        (
            20,
            -10,
            MessageHandler(
                filters.Regex(r"^(منع|سماح)(?:\s+.+)?$"),
                permission_command,
            ),
        ),

        # تعديل الستارت
        (
            21,
            -8,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^(تعديل ستارت|الستارت)$"),
                start_editor_command,
            ),
        ),

        (
            22,
            -7,
            CallbackQueryHandler(
                start_editor_callback,
                pattern=(
                    r"^startedit:(?:menu|message|buttons|add_button|"
                    r"order_button|delete_button|access|image)$"
                ),
            ),
        ),

        (
            23,
            -7,
            CallbackQueryHandler(
                start_editor_special_callback,
                pattern=(
                    r"^startedit:(?:access_add|access_delete|"
                    r"image_add|image_delete|image_delete_all)$"
                ),
            ),
        ),

        (
            24,
            -8,
            MessageHandler(
                filters.ChatType.PRIVATE & ~filters.COMMAND,
                start_editor_message,
            ),
        ),

        # لوحة المطور
        (
            25,
            -10,
            CallbackQueryHandler(
                developer_panel_callback,
                pattern=r"^devpanel:",
            ),
        ),

        (
            26,
            -9,
            MessageHandler(
                filters.ChatType.PRIVATE & ~filters.COMMAND,
                developer_panel_message,
            ),
        ),

        (
            27,
            -10,
            ChatMemberHandler(
                track_bot_chat_member,
                ChatMemberHandler.MY_CHAT_MEMBER,
            ),
        ),

        # تشغيل الأوامر المضافة
        (
            28,
            -7,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                custom_command_alias_handler,
            ),
        ),

        # الرسائل المؤقتة
        (
            29,
            -8,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(
                    r"^(?:اضف رسالة مؤقتة|اضف رساله مؤقته"
                    r"|الرسائل المؤقتة|الرسائل المؤقته"
                    r"|مسح الرس(?:الة|اله) المؤقت(?:ة|ه)\s+\d+"
                    r"|مسح الرسائل المؤقتة|مسح الرسائل المؤقته"
                    r"|ضع الرسالة\s+\d+)(?: عام)?$"
                ),
                temporary_message_command,
            ),
        ),

        (
            30,
            48,
            CallbackQueryHandler(
                temporary_message_callback,
                pattern=r"^tmp:",
            ),
        ),

        (
            31,
            49,
            MessageHandler(
                filters.ChatType.GROUPS
                & (
                    filters.TEXT
                    | filters.PHOTO
                    | filters.VIDEO
                    | filters.ANIMATION
                    | filters.Document.ALL
                    | filters.AUDIO
                    | filters.VOICE
                    | filters.VIDEO_NOTE
                    | filters.Sticker.ALL
                ),
                temporary_message_pending_handler_safe,
            ),
        ),

        # قفل وفتح الأوامر
        (
            63,
            0,
            MessageHandler(
                filters.Regex(r"^قفل امر .+$"),
                lock_command,
            ),
        ),

        (
            64,
            0,
            MessageHandler(
                filters.Regex(r"^فتح امر .+$"),
                open_command,
            ),
        ),

        (
            65,
            -13,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                save_lock_rank,
            ),
        ),

        # الهمسات - روابط البداية
        (
            66,
            0,
            MessageHandler(
                filters.Regex(
                    r"^/start\s+whisper_[A-Za-z0-9_-]+$"
                ),
                whisper_start,
            ),
        ),

        (
            67,
            -10,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^/start(?:\s.*)?$"),
                track_private_start,
            ),
        ),

        # البداية
        (
            68,
            0,
            CommandHandler(
                "start",
                start,
            ),
        ),

        # قائمة الأوامر
        (
            69,
            -5,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(
                    r"^/start(?:@\w+)?\s+commands$"
                ),
                commands_menu_start,
            ),
        ),

        (
            70,
            -5,
            CommandHandler(
                "help",
                commands_menu_start,
            ),
        ),

        (
            71,
            -8,
            MessageHandler(
                filters.Regex(r"^(?:الأوامر|الاوامر)$"),
                commands_menu_start,
            ),
        ),

        # الهمسات
        (
            117,
            0,
            MessageHandler(
                filters.Regex(r"^(همسه|همسة|اهمس)$"),
                whisper_command,
            ),
        ),

        (
            118,
            0,
            MessageHandler(
                filters.Regex(r"^تفعيل الهمسات$"),
                enable_whispers_command,
            ),
        ),

        (
            119,
            0,
            MessageHandler(
                filters.Regex(r"^تعطيل الهمسات$"),
                disable_whispers_command,
            ),
        ),

        (
            120,
            0,
            MessageHandler(
                filters.ChatType.PRIVATE,
                whisper_private_message,
            ),
        ),

        (
            121,
            -1,
            MessageHandler(
                filters.Regex(r"^الهمسات$"),
                whispers_list_command,
            ),
        ),

        # التسليات والبنك
        (
            125,
            -4,
            MessageHandler(
                filters.Regex(r"^عرض الاكواد$"),
                show_scratch_codes,
            ),
        ),

        (
            126,
            -4,
            MessageHandler(
                filters.Regex(r"^كشط\s+[A-Za-z0-9]+$"),
                scratch_code,
            ),
        ),

        (
            127,
            -4,
            MessageHandler(
                filters.Regex(r"^رست الكشط$"),
                reset_scratch_cooldown,
            ),
        ),

        (
            128,
            -4,
            MessageHandler(
                filters.Regex(r"^انشاء حساب بنكي$"),
                create_bank_account,
            ),
        ),

        (
            129,
            -4,
            MessageHandler(
                filters.Regex(r"^حسابي$"),
                my_bank_account,
            ),
        ),

        (
            130,
            -4,
            MessageHandler(
                filters.Regex(r"^مسح حسابي$"),
                delete_bank_account,
            ),
        ),

        (
            131,
            -4,
            MessageHandler(
                filters.Regex(r"^(راتب|راتبي)$"),
                salary,
            ),
        ),

        (
            132,
            -4,
            MessageHandler(
                filters.Regex(r"^بخشيش$"),
                tip,
            ),
        ),

        (
            133,
            -4,
            MessageHandler(
                filters.Regex(r"^المتجر$"),
                store,
            ),
        ),

        (
            134,
            -4,
            MessageHandler(
                filters.Regex(r"^ممتلكاتي$"),
                my_possessions,
            ),
        ),

        (
            135,
            -4,
            MessageHandler(
                filters.Regex(r"^ممتلكاته$"),
                other_possessions,
            ),
        ),

        (
            136,
            -4,
            MessageHandler(
                filters.Regex(r"^(شراء|بيع) \d+ \S+$"),
                buy_sell,
            ),
        ),

        (
            137,
            -4,
            MessageHandler(
                filters.Regex(r"^اهداء \d+ \S+$"),
                gift,
            ),
        ),

        (
            138,
            -4,
            MessageHandler(
                filters.Regex(r"^زرف$"),
                rob,
            ),
        ),

        (
            139,
            -4,
            MessageHandler(
                filters.Regex(r"^تحويل \d+$"),
                transfer,
            ),
        ),

        (
            140,
            -4,
            MessageHandler(
                filters.Regex(r"^\d{17}$"),
                transfer_account_number,
            ),
        ),

        (
            141,
            -4,
            MessageHandler(
                filters.Regex(r"^استثمار(?: نقاطي|\s+\d+)?$"),
                invest,
            ),
        ),

        (
            142,
            -4,
            MessageHandler(
                filters.Regex(r"^حظ(?: نقاطي|\s+\d+)?$"),
                luck,
            ),
        ),

        (
            143,
            -4,
            CallbackQueryHandler(
                bank_callback,
                pattern=r"^tasliyat:bank:",
            ),
        ),

        (
            144,
            -4,
            CallbackQueryHandler(
                transfer_message_callback,
                pattern=r"^tasliyat:transfer_message:",
            ),
        ),

        # لوحة المطور - الخاص
        (
            196,
            -10,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^اوامر المطور$"),
                developer_panel_command,
            ),
        ),

        # الهمسات - Callback
        (
            198,
            0,
            CallbackQueryHandler(
                whisper_callbacks,
                pattern=r"^wh_",
            ),
        ),

        # قائمة الأوامر - Callback
        (
            200,
            -4,
            CallbackQueryHandler(
                commands_menu_callback,
                pattern=r"^cmdmenu:",
            ),
        ),

        # حذف الرسائل
        (
            201,
            -3,
            MessageHandler(
                filters.Regex(r"^مسح(?:\s*\d+)?$"),
                delete_messages,
            ),
        ),
    ]
