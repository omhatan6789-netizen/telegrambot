
def register_all_handlers(app):
    """
    يجمع المعالجات من ملفات التسجيل المختلفة،
    ثم يسجلها مع المحافظة على ترتيبها الأصلي.
    """

    from .media import build_media_handlers
    from .moderation import build_moderation_handlers
    from .replies import build_replies_handlers
    from .users import build_users_handlers
    from .points import build_points_handlers
    from .games import build_games_handlers
    from .other import build_other_handlers

    handlers = []

    builders = (
        build_media_handlers,
        build_moderation_handlers,
        build_replies_handlers,
        build_users_handlers,
        build_points_handlers,
        build_games_handlers,
        build_other_handlers,
    )

    for builder in builders:
        handlers.extend(builder(app))

    # كل عنصر: (ترتيب التسجيل الأصلي، رقم المجموعة، المعالج)
    handlers.sort(key=lambda item: item[0])

    for _, group, handler in handlers:
        app.add_handler(handler, group=group)

    print(f"✅ تم تسجيل {len(handlers)} معالج بنجاح")
