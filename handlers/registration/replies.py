
from telegram.ext import MessageHandler, filters

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
    delete_all_special_replies,
)

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
    check_admin_profile_reply,
    profile_reply_pending_handler,
)


def build_replies_handlers(app):
    handlers = [

        # ==========================================
        # الردود الشخصية المعلقة
        # ==========================================

        (
            80,
            -11,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                profile_reply_pending_handler,
            ),
        ),

        # ==========================================
        # أوامر المطور والمالك وردود الإدارة
        # ==========================================

        (
            81,
            0,
            MessageHandler(
                filters.Regex(r"^المطور$"),
                developer_command,
            ),
        ),

        (
            82,
            0,
            MessageHandler(
                filters.Regex(r"^تغيير يوزر المطور$"),
                change_developer_username,
            ),
        ),

        (
            83,
            0,
            MessageHandler(
                filters.Regex(r"^المالك$"),
                owner_command,
            ),
        ),

        (
            84,
            0,
            MessageHandler(
                filters.Regex(r"^تغيير يوزر المالك$"),
                change_owner_username,
            ),
        ),

        (
            85,
            0,
            MessageHandler(
                filters.Regex(r"^اضف ردي$"),
                add_my_admin_reply,
            ),
        ),

        (
            86,
            0,
            MessageHandler(
                filters.Regex(r"^حذف ردي$"),
                delete_my_admin_reply,
            ),
        ),

        (
            87,
            0,
            MessageHandler(
                filters.Regex(r"^حذف رده$"),
                delete_other_admin_reply,
            ),
        ),

        (
            88,
            0,
            MessageHandler(
                filters.Regex(r"^ردود الادمن$"),
                admin_replies_list,
            ),
        ),

        (
            89,
            0,
            MessageHandler(
                filters.Regex(r"^تفعيل ردود الادمن$"),
                enable_admin_replies,
            ),
        ),

        (
            90,
            0,
            MessageHandler(
                filters.Regex(r"^تعطيل ردود الادمن$"),
                disable_admin_replies,
            ),
        ),

        (
            91,
            0,
            MessageHandler(
                filters.Regex(r"^حذف ردود الادمن$"),
                delete_all_admin_replies_command,
            ),
        ),

        (
            92,
            39,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                check_admin_profile_reply,
            ),
        ),

        # ==========================================
        # الردود المميزة
        # ==========================================

        (
            96,
            0,
            MessageHandler(
                filters.Regex(r"^اضف رد مميز$"),
                add_special_reply_start,
            ),
        ),

        (
            97,
            2,
            MessageHandler(
                filters.ALL,
                add_special_reply_handler,
            ),
        ),

        (
            98,
            0,
            MessageHandler(
                filters.Regex(r"^تعديل رد مميز$"),
                edit_special_reply_start,
            ),
        ),

        (
            99,
            3,
            MessageHandler(
                filters.ALL,
                edit_special_reply_handler,
            ),
        ),

        (
            100,
            0,
            MessageHandler(
                filters.Regex(r"^مسح رد مميز$"),
                delete_special_reply_start,
            ),
        ),

        (
            101,
            4,
            MessageHandler(
                filters.ALL,
                delete_special_reply_handler,
            ),
        ),

        (
            102,
            0,
            MessageHandler(
                filters.Regex(r"^الردود المميزة$"),
                special_replies_list,
            ),
        ),

        # ==========================================
        # الردود العادية
        # ==========================================

        (
            103,
            -6,
            MessageHandler(
                filters.Regex(r"^اضف رد$"),
                add_reply_start,
            ),
        ),

        (
            104,
            5,
            MessageHandler(
                filters.ALL,
                add_reply_handler,
            ),
        ),

        (
            105,
            0,
            MessageHandler(
                filters.Regex(r"^تعديل رد$"),
                edit_reply_start,
            ),
        ),

        (
            106,
            6,
            MessageHandler(
                filters.ALL,
                edit_reply_handler,
            ),
        ),

        (
            107,
            0,
            MessageHandler(
                filters.Regex(r"^مسح رد$"),
                delete_reply_start,
            ),
        ),

        (
            108,
            7,
            MessageHandler(
                filters.ALL,
                delete_reply_handler,
            ),
        ),

        (
            109,
            0,
            MessageHandler(
                filters.Regex(r"^الردود$"),
                replies_list,
            ),
        ),

        (
            110,
            0,
            MessageHandler(
                filters.Regex(r"^مسح الردود$"),
                delete_all_replies,
            ),
        ),

        (
            111,
            0,
            MessageHandler(
                filters.Regex(r"^مسح الردود المميزة$"),
                delete_all_special_replies,
            ),
        ),

        # ==========================================
        # تشغيل الردود التلقائية
        # ==========================================

        (
            165,
            40,
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                check_replies,
            ),
        ),
    ]

    return handlers
