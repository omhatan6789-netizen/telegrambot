
from telegram import Update
from telegram.ext import (
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==================================================
# الموسيقى واليوتي
# ==================================================

from handlers.music import (
    music_message_handler,
    music_callback,
    voice_chat_started,
    voice_chat_ended,
)

from handlers.youtube_audio import (
    youtube_audio_search,
    youtube_audio_callback,
)

from ai_assistant import ai_assistant_message

from handlers.emoji_reactions import emoji_reactions_handler


# ==================================================
# الإرسال
# ==================================================

from handlers.send import (
    send_command,
    delete_slash_command,
    handle_send_media,
)

from handlers.tasliyat import (
    transfer_message_receiver,
    transfer_message_callback,
)


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
    WAIT_NEW,
)


# ==================================================
# الصلاحيات وقفل الأوامر
# ==================================================

from permissions import permission_command

from handlers.command_lock import (
    lock_command,
    save_lock_rank,
    open_command,
)


# ==================================================
# تعديل الستارت
# ==================================================

from handlers.start_editor import (
    start_editor_command,
    start_editor_callback,
    start_editor_special_callback,
    start_editor_message,
)


# ==================================================
# لوحة المطور
# ==================================================

from handlers.developer_panel import (
    developer_panel_command,
    developer_panel_callback,
    developer_panel_message,
    track_private_start,
    track_bot_chat_member,
)


# ==================================================
# الرسائل المؤقتة
# ==================================================

from handlers.temporary_messages import (
    temporary_message_command,
    temporary_message_pending_handler,
    temporary_message_callback,
)


# ==================================================
# البداية وقائمة الأوامر
# ==================================================

from handlers.start import start

from handlers.commands_menu import (
    commands_menu_start,
    commands_menu_callback,
)


# ==================================================
# الملفات الشخصية وردود الإدارة
# ==================================================

from handlers.profile_replies import (
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


# ==================================================
# التسليات
# ==================================================

from handlers.tasliyat import (
    show_scratch_codes,
    scratch_code,
    reset_scratch_cooldown,
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
    invest,
    luck,
)


# ==================================================
# حذف الرسائل
# ==================================================

from handlers.delete_messages import delete_messages


# ==================================================
# الردود العامة
# ==================================================

from handlers.replies import check_replies


def build_other_handlers(app):

    handlers = []

    # ==================================================
    # الموسيقى واليوتي وميزات الذكاء الاصطناعي
    # ==================================================

    handlers.extend([
        (
            1,
            -1002,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                music_message_handler,
            )
        ),

        (
            2,
            -1001,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND
                & filters.Regex(r"^(?:بحث|يوت)\s+.+$"),
                youtube_audio_search,
            )
        ),

        (
            3,
            -4,
            CallbackQueryHandler(
                youtube_audio_callback,
                pattern=r"^ytpick:",
            )
        ),

        (
            4,
            -4,
            CallbackQueryHandler(
                music_callback,
                pattern=r"^musicpick:",
            )
        ),

        (
            5,
            -4,
            MessageHandler(
                filters.StatusUpdate.VIDEO_CHAT_STARTED,
                voice_chat_started,
            )
        ),

        (
            6,
            -4,
            MessageHandler(
                filters.StatusUpdate.VIDEO_CHAT_ENDED,
                voice_chat_ended,
            )
        ),

        (
            7,
            -1000,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                ai_assistant_message,
            )
        ),

        (
            8,
            -1001,
            MessageHandler(
                filters.TEXT,
                emoji_reactions_handler,
            )
        ),
    ])

    # ==================================================
    # الإرسال
    # ==================================================

    handlers.extend([
        (
            11,
            -30,
            MessageHandler(
                filters.Regex(
                    r"^/send(?:@[A-Za-z0-9_]+)?(?:\s+[\s\S]+)?$"
                ),
                send_command,
            )
        ),

        (
            12,
            -29,
            MessageHandler(
                filters.ChatType.PRIVATE
                & ~filters.COMMAND,
                transfer_message_receiver,
            )
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
            )
        ),

        (
            14,
            -27,
            MessageHandler(
                filters.Regex(r"^/[\s\S]+$"),
                delete_slash_command,
            )
        ),
    ])

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

    handlers.extend([
        (15, -2, add_command_conv),

        (
            16,
            0,
            MessageHandler(
                filters.Regex(r"^الاوامر المضافة$"),
                custom_commands_list
            )
        ),

        (
            17,
            0,
            MessageHandler(
                filters.Regex(r"^مسح امر$"),
                delete_command_start
            )
        ),

        (
            18,
            -2,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                delete_command
            )
        ),

        (
            19,
            0,
            MessageHandler(
                filters.Regex(r"^مسح الاوامر المضافة$"),
                delete_all_commands
            )
        ),
    ])

    # ==================================================
    # الصلاحيات
    # ==================================================

    handlers.append(
        (
            20,
            -10,
            MessageHandler(
                filters.Regex(r"^(منع|سماح)(?:\s+.+)?$"),
                permission_command
            )
        )
    )

    # ==================================================
    # تعديل الستارت
    # ==================================================

    handlers.extend([
        (
            21,
            -8,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^(تعديل ستارت|الستارت)$"),
                start_editor_command
            )
        ),

        (
            22,
            -7,
            CallbackQueryHandler(
                start_editor_callback,
                pattern=(
                    r"^startedit:(?:menu|message|buttons|add_button|"
                    r"order_button|delete_button|access|image)$"
                )
            )
        ),

        (
            23,
            -7,
            CallbackQueryHandler(
                start_editor_special_callback,
                pattern=(
                    r"^startedit:(?:access_add|access_delete|"
                    r"image_add|image_delete|image_delete_all)$"
                )
            )
        ),

        (
            24,
            -8,
            MessageHandler(
                filters.ChatType.PRIVATE & ~filters.COMMAND,
                start_editor_message
            )
        ),
    ])

    # ==================================================
    # لوحة المطور
    # ==================================================

    handlers.extend([
        (
            25,
            -10,
            CallbackQueryHandler(
                developer_panel_callback,
                pattern=r"^devpanel:"
            )
        ),

        (
            26,
            -9,
            MessageHandler(
                filters.ChatType.PRIVATE
                & ~filters.COMMAND,
                developer_panel_message
            )
        ),

        (
            27,
            -10,
            ChatMemberHandler(
                track_bot_chat_member,
                ChatMemberHandler.MY_CHAT_MEMBER
            )
        ),
    ])

    # ==================================================
    # تشغيل الأوامر المضافة
    # ==================================================

    async def custom_command_alias_handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        from custom_commands import is_alias_execution

        if is_alias_execution(update):
            return

        executed = await check_custom_commands(
            update,
            context,
            application=app
        )

        if executed:
            raise ApplicationHandlerStop()

    handlers.append(
        (
            28,
            -7,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                custom_command_alias_handler
            )
        )
    )

    # ==================================================
    # الرسائل المؤقتة
    # ==================================================

    handlers.extend([
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
            )
        ),

        (
            30,
            48,
            CallbackQueryHandler(
                temporary_message_callback,
                pattern=r"^tmp:",
            )
        ),
    ])

    async def temporary_message_pending_handler_safe(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        from custom_commands import is_alias_execution

        if is_alias_execution(update):
            return

        await temporary_message_pending_handler(
            update,
            context
        )

    handlers.append(
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
            )
        )
    )

    # ==================================================
    # قفل وفتح الأوامر
    # ==================================================

    handlers.extend([
        (
            63,
            0,
            MessageHandler(
                filters.Regex(r"^قفل امر .+$"),
                lock_command
            )
        ),

        (
            64,
            0,
            MessageHandler(
                filters.Regex(r"^فتح امر .+$"),
                open_command
            )
        ),

        (
            65,
            -13,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                save_lock_rank
            )
        ),
    ])

    # ==================================================
    # الهمسات والبداية
    # ==================================================

    handlers.extend([
        (
            66,
            0,
            MessageHandler(
                filters.Regex(
                    r"^/start\s+whisper_[A-Za-z0-9_-]+$"
                ),
                whisper_start,
            )
        ),

        (
            67,
            -10,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^/start(?:\s.*)?$"),
                track_private_start
            )
        ),

        (
            68,
            0,
            CommandHandler(
                "start",
                start
            )
        ),

        (
            69,
            -5,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(
                    r"^/start(?:@\w+)?\s+commands$"
                ),
                commands_menu_start
            )
        ),

        (
            70,
            -5,
            CommandHandler(
                "help",
                commands_menu_start
            )
        ),

        (
            71,
            -8,
            MessageHandler(
                filters.Regex(r"^(?:الأوامر|الاوامر)$"),
                commands_menu_start
            )
        ),
    ])

    # ==================================================
    # الملفات الشخصية وردود الإدارة
    # ==================================================

    handlers.extend([
        (
            80,
            0,
            MessageHandler(
                filters.Regex(r"^المطور$"),
                developer_command
            )
        ),

        (
            81,
            0,
            MessageHandler(
                filters.Regex(r"^تغيير يوزر المطور$"),
                change_developer_username
            )
        ),

        (
            82,
            0,
            MessageHandler(
                filters.Regex(r"^المالك$"),
                owner_command
            )
        ),

        (
            83,
            0,
            MessageHandler(
                filters.Regex(r"^تغيير يوزر المالك$"),
                change_owner_username
            )
        ),

        (
            84,
            0,
            MessageHandler(
                filters.Regex(r"^اضف ردي$"),
                add_my_admin_reply
            )
        ),

        (
            85,
            0,
            MessageHandler(
                filters.Regex(r"^حذف ردي$"),
                delete_my_admin_reply
            )
        ),

        (
            86,
            0,
            MessageHandler(
                filters.Regex(r"^حذف رده$"),
                delete_other_admin_reply
            )
        ),

        (
            87,
            0,
            MessageHandler(
                filters.Regex(r"^ردود الادمن$"),
                admin_replies_list
            )
        ),

        (
            88,
            0,
            MessageHandler(
                filters.Regex(r"^تفعيل ردود الادمن$"),
                enable_admin_replies
            )
        ),

        (
            89,
            0,
            MessageHandler(
                filters.Regex(r"^تعطيل ردود الادمن$"),
                disable_admin_replies
            )
        ),

        (
            90,
            0,
            MessageHandler(
                filters.Regex(r"^حذف ردود الادمن$"),
                delete_all_admin_replies_command
            )
        ),
    ])

    # ==================================================
    # الهمسات
    # ==================================================

    handlers.extend([
        (
            116,
            0,
            MessageHandler(
                filters.Regex(r"^(همسه|همسة|اهمس)$"),
                whisper_command,
            )
        ),

        (
            117,
            0,
            MessageHandler(
                filters.Regex(r"^تفعيل الهمسات$"),
                enable_whispers_command,
            )
        ),

        (
            118,
            0,
            MessageHandler(
                filters.Regex(r"^تعطيل الهمسات$"),
                disable_whispers_command,
            )
        ),

        (
            119,
            0,
            MessageHandler(
                filters.ChatType.PRIVATE,
                whisper_private_message,
            )
        ),

        (
            120,
            -1,
            MessageHandler(
                filters.Regex(r"^الهمسات$"),
                whispers_list_command,
            )
        ),
    ])

    # ==================================================
    # التسليات
    # ==================================================

    handlers.extend([
        (
            124,
            -4,
            MessageHandler(
                filters.Regex(r"^عرض الاكواد$"),
                show_scratch_codes,
            )
        ),

        (
            125,
            -4,
            MessageHandler(
                filters.Regex(r"^كشط\s+[A-Za-z0-9]+$"),
                scratch_code
            )
        ),

        (
            126,
            -4,
            MessageHandler(
                filters.Regex(r"^رست الكشط$"),
                reset_scratch_cooldown
            )
        ),

        (
            127,
            -4,
            MessageHandler(
                filters.Regex(r"^انشاء حساب بنكي$"),
                create_bank_account
            )
        ),

        (
            128,
            -4,
            MessageHandler(
                filters.Regex(r"^حسابي$"),
                my_bank_account
            )
        ),

        (
            129,
            -4,
            MessageHandler(
                filters.Regex(r"^مسح حسابي$"),
                delete_bank_account
            )
        ),

        (
            130,
            -4,
            MessageHandler(
                filters.Regex(r"^(راتب|راتبي)$"),
                salary
            )
        ),

        (
            131,
            -4,
            MessageHandler(
                filters.Regex(r"^بخشيش$"),
                tip
            )
        ),

        (
            132,
            -4,
            MessageHandler(
                filters.Regex(r"^المتجر$"),
                store
            )
        ),

        (
            133,
            -4,
            MessageHandler(
                filters.Regex(r"^ممتلكاتي$"),
                my_possessions
            )
        ),

        (
            134,
            -4,
            MessageHandler(
                filters.Regex(r"^ممتلكاته$"),
                other_possessions
            )
        ),

        (
            135,
            -4,
            MessageHandler(
                filters.Regex(r"^(شراء|بيع) \d+ \S+$"),
                buy_sell
            )
        ),

        (
            136,
            -4,
            MessageHandler(
                filters.Regex(r"^اهداء \d+ \S+$"),
                gift
            )
        ),

        (
            137,
            -4,
            MessageHandler(
                filters.Regex(r"^زرف$"),
                rob
            )
        ),

        (
            138,
            -4,
            MessageHandler(
                filters.Regex(r"^تحويل \d+$"),
                transfer
            )
        ),

        (
            139,
            -4,
            MessageHandler(
                filters.Regex(r"^\d{17}$"),
                transfer_account_number
            )
        ),

        (
            140,
            -4,
            MessageHandler(
                filters.Regex(r"^استثمار(?: نقاطي|\s+\d+)?$"),
                invest
            )
        ),

        (
            141,
            -4,
            MessageHandler(
                filters.Regex(r"^حظ(?: نقاطي|\s+\d+)?$"),
                luck
            )
        ),

        (
            142,
            -4,
            CallbackQueryHandler(
                bank_callback,
                pattern=r"^tasliyat:bank:"
            )
        ),

        (
            143,
            -4,
            CallbackQueryHandler(
                transfer_message_callback,
                pattern=r"^tasliyat:transfer_message:"
            )
        ),
    ])

    # ==================================================
    # الردود العامة
    # ==================================================

    handlers.append(
        (
            164,
            40,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                check_replies
            )
        )
    )

    # ==================================================
    # لوحة المطور - الخاص
    # ==================================================

    handlers.append(
        (
            195,
            -10,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(r"^اوامر المطور$"),
                developer_panel_command
            )
        )
    )

    # ==================================================
    # Callback الهمسات
    # ==================================================

    handlers.append(
        (
            197,
            0,
            CallbackQueryHandler(
                whisper_callbacks,
                pattern=r"^wh_",
            )
        )
    )

    # ==================================================
    # Callback قائمة الأوامر
    # ==================================================

    handlers.append(
        (
            199,
            -4,
            CallbackQueryHandler(
                commands_menu_callback,
                pattern=r"^cmdmenu:"
            )
        )
    )

    # ==================================================
    # حذف الرسائل
    # ==================================================

    handlers.append(
        (
            200,
            -3,
            MessageHandler(
                filters.Regex(r"^مسح(?:\s*\d+)?$"),
                delete_messages
            )
        )
    )

    return handlers
