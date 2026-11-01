
from telegram.ext import MessageHandler, filters

from handlers.users import (
    user_id_command,
    save_join_date,
    save_user_message,
)

from handlers.roles import (
    roles_command,
    change_rank,
    roles_clear_callback,
)

from handlers.developer_panel import (
    clear_dev_command,
    clear_rank_command,
    clear_all_ranks_command,
)


def build_users_handlers(app):
    handlers = [
        # معلومات المستخدمين
        (72, 0, user_id_command),
        (73, 0, roles_command),

        # أوامر إدارة الرتب
        (74, -9, roles_command),
        (75, -9, clear_dev_command),
        (76, -9, clear_rank_command),
        (77, -9, clear_all_ranks_command),
        (78, -9, roles_clear_callback),

        # كشف المجموعة
        (92, 0, roles_command),

        # تغيير الرتب
        (93, -9, change_rank),
        (94, 0, change_rank),

        # تتبع الأعضاء والرسائل
        (165, 0, save_join_date),
        (166, 50, save_user_message),
    ]

    return [
        (index, group, handler)
        for index, group, handler in handlers
    ]
