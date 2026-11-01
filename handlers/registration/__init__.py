
def register_all_handlers(app):
    from .media import build_media_handlers
    from .moderation import build_moderation_handlers
    from .replies import build_replies_handlers
    from .users import build_users_handlers
    from .points import build_points_handlers
    from .games import build_games_handlers
    from .other import build_other_handlers

    builders = [
        build_media_handlers,
        build_moderation_handlers,
        build_replies_handlers,
        build_users_handlers,
        build_points_handlers,
        build_games_handlers,
        build_other_handlers,
    ]

    handlers = []

    for builder in builders:
        result = builder(app)

        if not isinstance(result, list):
            raise TypeError(
                f"{builder.__name__} يجب أن تعيد قائمة handlers"
            )

        handlers.extend(result)

    # التأكد من صحة بيانات التسجيل
    for item in handlers:
        if not isinstance(item, tuple) or len(item) != 3:
            raise ValueError(
                f"صيغة تسجيل غير صحيحة: {item!r}"
            )

        index, group, handler = item

        if not isinstance(index, int):
            raise TypeError(
                f"رقم ترتيب غير صحيح: {index!r}"
            )

        if not isinstance(group, int):
            raise TypeError(
                f"رقم مجموعة غير صحيح عند الترتيب {index}"
            )

    # منع تكرار أرقام الترتيب
    indices = [item[0] for item in handlers]

    if len(indices) != len(set(indices)):
        duplicates = sorted({
            index
            for index in indices
            if indices.count(index) > 1
        })

        raise ValueError(
            f"❌ يوجد تكرار في أرقام تسجيل المعالجات: {duplicates}"
        )

    # الترتيب الأصلي من main.py
    handlers.sort(key=lambda item: item[0])

    # تسجيل المعالجات
    for index, group, handler in handlers:
        app.add_handler(
            handler,
            group=group
        )

    print(
        f"✅ تم تسجيل {len(handlers)} معالج بنجاح"
    )
