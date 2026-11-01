
from telegram.ext import MessageHandler, filters

from handlers.replies import (
    add_special_reply_start,
    add_special_reply_handler,
    edit_special_reply_start,
    edit_special_reply_handler,
    delete_special_reply_start,
    delete_special_reply_handler,
    special_replies_list,
    add_reply_start,
    add_reply_handler,
    edit_reply_start,
    edit_reply_handler,
    delete_reply_start,
    delete_reply_handler,
    replies_list,
    delete_all_replies,
    delete_all_special_replies,
)

from handlers.profile_replies import (
    profile_reply_pending_handler,
    check_admin_profile_reply,
)


def build_replies_handlers(app):
    handlers = [
        # ردود المشرفين والملف الشخصي
        (79, -11, profile_reply_pending_handler),
        (91, 39, check_admin_profile_reply),

        # الردود الخاصة
        (95, 0, add_special_reply_start),
        (96, 2, MessageHandler(filters.ALL, add_special_reply_handler)),
        (97, 0, edit_special_reply_start),
        (98, 3, MessageHandler(filters.ALL, edit_special_reply_handler)),
        (99, 0, delete_special_reply_start),
        (100, 4, MessageHandler(filters.ALL, delete_special_reply_handler)),
        (101, 0, special_replies_list),

        # الردود العادية
        (102, -6, add_reply_start),
        (103, 5, MessageHandler(filters.ALL, add_reply_handler)),
        (104, 0, edit_reply_start),
        (105, 6, MessageHandler(filters.ALL, edit_reply_handler)),
        (106, 0, delete_reply_start),
        (107, 7, MessageHandler(filters.ALL, delete_reply_handler)),
        (108, 0, replies_list),
        (109, 0, delete_all_replies),
        (110, 0, delete_all_special_replies),
    ]

    return [
        (index, group, handler)
        for index, group, handler in handlers
    ]
