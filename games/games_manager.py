from telegram import Update
from telegram.ext import ContextTypes

from database import connect

import random


# ==================================================
# الألعاب النشطة
# ==================================================

active_games = {}


# ==================================================
# صاحب البوت
# ==================================================

OWNER_ID = 8453977662


# ==================================================
# جلسات إضافة لعبة
# ==================================================

add_game_sessions = {}


# ==================================================
# جلسات إضافة سؤال
# ==================================================

add_question_sessions = {}


# ==================================================
# Cache الألعاب والأسئلة
# ==================================================

games_cache = None
game_questions_cache = None
games_settings_cache = None

_game_admin_cache = {}


# ==================================================
# تحميل كاش الألعاب
# ==================================================

def load_games_cache():

    global games_cache
    global game_questions_cache
    global games_settings_cache

    conn = connect()

    try:

        cur = conn.cursor()

        # --------------------------------------------------
        # الألعاب
        # --------------------------------------------------

        cur.execute(
            """
            SELECT name, status
            FROM games
            """
        )

        games = cur.fetchall()

        games_cache = {
            row[0]: row[1]
            for row in games
        }

        # --------------------------------------------------
        # الأسئلة
        # --------------------------------------------------

        cur.execute(
            """
            SELECT
                id,
                game_name,
                question,
                image,
                caption,
                answers
            FROM game_questions
            """
        )

        questions = cur.fetchall()

        game_questions_cache = {}

        for row in questions:

            question_id = row[0]
            game_name = row[1]

            question_data = (
                question_id,
                row[2],
                row[3],
                row[4],
                row[5]
            )

            game_questions_cache.setdefault(
                game_name,
                []
            ).append(question_data)

        # --------------------------------------------------
        # حالة جميع الألعاب
        # --------------------------------------------------

        cur.execute(
            """
            SELECT status
            FROM games_settings
            WHERE id=1
            """
        )

        settings = cur.fetchone()

        if settings:
            games_settings_cache = settings[0]
        else:
            games_settings_cache = "on"

        try:
            cur.close()
        except Exception:
            pass

    finally:

        conn.close()


# ==================================================
# تحديث كاش الألعاب
# ==================================================

def invalidate_games_cache():

    global games_cache
    global game_questions_cache
    global games_settings_cache

    games_cache = None
    game_questions_cache = None
    games_settings_cache = None


# ==================================================
# الحصول على كاش الألعاب
# ==================================================

def get_games_cache():

    global games_cache
    global game_questions_cache
    global games_settings_cache

    if (
        games_cache is None
        or game_questions_cache is None
        or games_settings_cache is None
    ):
        load_games_cache()

    return (
        games_cache,
        game_questions_cache,
        games_settings_cache
    )


# ==================================================
# صلاحيات إدارة الألعاب
# ==================================================

async def is_game_admin(user_id):

    if user_id == OWNER_ID:
        return True

    # --------------------------------------------------
    # كاش مؤقت للصلاحية
    # --------------------------------------------------

    if user_id in _game_admin_cache:
        return _game_admin_cache[user_id]

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT rank
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        data = cur.fetchone()

        try:
            cur.close()
        except Exception:
            pass

    finally:

        conn.close()

    if not data:

        _game_admin_cache[user_id] = False

        return False

    allowed = data[0] in [
        " نائب المالك",
        "ادمن اساسي",
        "ادمن"
    ]

    _game_admin_cache[user_id] = allowed

    return allowed


# ==================================================
# بدء إضافة لعبة
# ==================================================

async def add_game_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if not await is_game_admin(user_id):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    # --------------------------------------------------
    # إغلاق جلسات الردود
    # --------------------------------------------------

    try:

        from handlers.replies import (
            add_reply_sessions,
            add_special_reply_sessions
        )

        add_reply_sessions.pop(
            user_id,
            None
        )

        add_special_reply_sessions.pop(
            user_id,
            None
        )

    except Exception:
        pass

    # --------------------------------------------------
    # بدء الجلسة
    # --------------------------------------------------

    add_game_sessions[user_id] = {
        "step": "name"
    }

    await update.message.reply_text(
        "حسنًا، أرسل اسم اللعبة التي تريد إضافتها"
    )


# ==================================================
# استقبال اسم اللعبة
# ==================================================

async def add_game_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if user_id not in add_game_sessions:
        return

    text = update.message.text

    if not text:
        return

    # --------------------------------------------------
    # منع حفظ الأوامر كلعبة
    # --------------------------------------------------

    if text.startswith(
        (
            "اضف",
            "حذف",
            "تعديل",
            "تفعيل",
            "تعطيل"
        )
    ):
        return

    game_name = text.strip()

    # --------------------------------------------------
    # التأكد من عدم وجود اللعبة
    # --------------------------------------------------

    games, _, _ = get_games_cache()

    if game_name in games:

        del add_game_sessions[user_id]

        await update.message.reply_text(
            "❌ اللعبة موجودة مسبقًا"
        )

        return

    # --------------------------------------------------
    # إضافة اللعبة
    # --------------------------------------------------

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO games
            (
                name,
                status
            )
            VALUES
            (
                ?,
                'on'
            )
            """,
            (game_name,)
        )

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    del add_game_sessions[user_id]

    await update.message.reply_text(
        f"✅ تم إضافة اللعبة: {game_name}\n\n"
        f"لإضافة أسئلة استخدم:\n"
        f"اضف سؤال {game_name}"
    )


# ==================================================
# عرض الألعاب
# ==================================================

async def games_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    games, _, _ = get_games_cache()

    if not games:

        await update.message.reply_text(
            "❌ لا توجد ألعاب مضافة"
        )

        return

    text = "🎮 الألعاب الموجودة:\n\n"

    for name, status in sorted(
        games.items(),
        key=lambda x: x[0]
    ):

        status_icon = (
            "🟢"
            if status == "on"
            else "🔴"
        )

        text += (
            f"{status_icon} {name}\n"
        )

    await update.message.reply_text(
        text
    )


# ==================================================
# حذف لعبة
# ==================================================

async def delete_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    name = update.message.text.replace(
        "حذف لعبة",
        ""
    ).strip()

    if not name:

        await update.message.reply_text(
            "❌ اكتب اسم اللعبة"
        )

        return

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM games
            WHERE name=?
            """,
            (name,)
        )

        cur.execute(
            """
            DELETE FROM game_questions
            WHERE game_name=?
            """,
            (name,)
        )

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    await update.message.reply_text(
        f"✅ تم حذف اللعبة: {name}"
    )


# ==================================================
# بدء إضافة سؤال
# ==================================================

async def add_question_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if not await is_game_admin(user_id):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    game_name = update.message.text.replace(
        "اضف سؤال",
        "",
        1
    ).strip()

    if not game_name:

        await update.message.reply_text(
            "❌ اكتب اسم اللعبة\n\n"
            "مثال:\n"
            "اضف سؤال تفكيك"
        )

        return

    # --------------------------------------------------
    # البحث من الكاش بدل DB
    # --------------------------------------------------

    games, _, _ = get_games_cache()

    if game_name not in games:

        await update.message.reply_text(
            "❌ اللعبة غير موجودة"
        )

        return

    # --------------------------------------------------
    # إنشاء جلسة السؤال
    # --------------------------------------------------

    add_question_sessions[user_id] = {

        "game": game_name,

        "step": "question",

        "answers": [],

        "ignore_next": True
    }

    await update.message.reply_text(
        f"✅ جاري إضافة سؤال للعبة: {game_name}\n\n"
        "📩 أرسل السؤال الآن.\n"
        "يمكنك إرسال:\n"
        "- نص فقط\n"
        "- أو صورة مع كابشن."
    )


# ==================================================
# استقبال السؤال والإجابات
# ==================================================

async def add_question_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if user_id not in add_question_sessions:
        return

    session = add_question_sessions[user_id]

    # --------------------------------------------------
    # تجاهل رسالة الأمر نفسها
    # --------------------------------------------------

    if session.get("ignore_next"):

        session["ignore_next"] = False

        return

    # ==================================================
    # استقبال السؤال
    # ==================================================

    if session["step"] == "question":

        image = None
        caption = None

        if update.message.photo:

            image = update.message.photo[-1].file_id

            caption = update.message.caption

            question = (
                caption
                if caption
                else "ما الإجابة؟"
            )

        elif update.message.text:

            question = update.message.text.strip()

        else:

            await update.message.reply_text(
                "❌ أرسل السؤال كنص أو صورة."
            )

            return

        session["question"] = question

        session["image"] = image

        session["caption"] = caption

        session["step"] = "answers"

        await update.message.reply_text(
            "✍️ أرسل الإجابات الصحيحة.\n"
            "كل إجابة في رسالة مستقلة.\n\n"
            "وعند الانتهاء اكتب:\n"
            "تم"
        )

        return

    # ==================================================
    # استقبال الإجابات
    # ==================================================

    if session["step"] == "answers":

        if not update.message.text:
            return

        text = update.message.text.strip()

        # --------------------------------------------------
        # حفظ السؤال
        # --------------------------------------------------

        if text == "تم":

            if not session["answers"]:

                await update.message.reply_text(
                    "❌ أضف إجابة واحدة على الأقل."
                )

                return

            conn = connect()

            try:

                cur = conn.cursor()

                cur.execute(
                    """
                    INSERT INTO game_questions
                    (
                        game_name,
                        question,
                        image,
                        caption,
                        answers
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session["game"],
                        session["question"],
                        session["image"],
                        session["caption"],
                        "|".join(
                            session["answers"]
                        )
                    )
                )

                conn.commit()

                try:
                    cur.close()
                except Exception:
                    pass

            except Exception:

                try:
                    conn.rollback()
                except Exception:
                    pass

                raise

            finally:

                conn.close()

            # --------------------------------------------------
            # تحديث الكاش
            # --------------------------------------------------

            invalidate_games_cache()

            del add_question_sessions[user_id]

            await update.message.reply_text(
                "✅ تم حفظ السؤال بنجاح."
            )

            return

        session["answers"].append(text)

        await update.message.reply_text(
            "✅ تمت إضافة الإجابة."
        )


# ==================================================
# تشغيل اللعبة
# ==================================================

async def play_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    chat_id = update.effective_chat.id

    # --------------------------------------------------
    # إذا فيه لعبة شغالة
    # --------------------------------------------------

    if chat_id in active_games:
        return

    # --------------------------------------------------
    # منع أوامر الإدارة من الدخول هنا
    # --------------------------------------------------

    blocked = (
        "اضف لعبة",
        "اضف سؤال",
        "حذف سؤال",
        "حذف لعبة",
        "تفعيل لعبة",
        "تعطيل لعبة",
        "تفعيل الالعاب",
        "تعطيل الالعاب",
        "الالعاب",
        "اسئلة"
    )

    if text.startswith(blocked):
        return

    # ==================================================
    # الكاش
    # ==================================================

    games, game_questions, games_settings = (
        get_games_cache()
    )

    # --------------------------------------------------
    # الألعاب كلها معطلة
    # --------------------------------------------------

    if games_settings == "off":
        return

    # --------------------------------------------------
    # ليست لعبة
    #
    # هذا هو أهم شيء في السرعة:
    # إذا الاسم غير موجود بالكاش نخرج فورًا
    # بدون أي اتصال بقاعدة البيانات.
    # --------------------------------------------------

    if text not in games:
        return

    # --------------------------------------------------
    # اللعبة معطلة
    # --------------------------------------------------

    if games[text] == "off":

        await update.message.reply_text(
            "❌ هذه اللعبة معطلة"
        )

        return

    # --------------------------------------------------
    # جلب أسئلة اللعبة من الكاش
    # --------------------------------------------------

    questions = game_questions.get(
        text,
        []
    )

    if not questions:

        await update.message.reply_text(
            "❌ لا توجد أسئلة لهذه اللعبة"
        )

        return

    # ==================================================
    # اختيار سؤال عشوائي
    # ==================================================

    question = random.choice(
        questions
    )

    raw_answers = question[4] or ""

    answers = [
        x.strip().casefold()
        for x in raw_answers.split("|")
        if x.strip()
    ]

    if not answers:

        await update.message.reply_text(
            "❌ هذا السؤال لا يحتوي على إجابة صحيحة"
        )

        return

    # ==================================================
    # حفظ اللعبة النشطة
    # ==================================================

    active_games[chat_id] = {

        "answers": answers,

        "winner": False,

        "game": text
    }

    question_text = (
        f"❓ {question[1]}\n\n"
        "أول واحد يجاوب ياخذ\n"
        "⭐ +3 نقاط"
    )

    # ==================================================
    # إرسال السؤال
    # ==================================================

    if question[2]:

        await update.message.reply_photo(
            photo=question[2],
            caption=question_text
        )

    else:

        await update.message.reply_text(
            question_text
        )


# ==================================================
# فحص الإجابات
# ==================================================

async def check_game_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    user_id = update.effective_user.id

    chat_id = update.effective_chat.id

    # --------------------------------------------------
    # إذا كان المستخدم يضيف سؤال
    # --------------------------------------------------

    if user_id in add_question_sessions:
        return

    # --------------------------------------------------
    # لا توجد لعبة
    # --------------------------------------------------

    if chat_id not in active_games:
        return

    game = active_games[chat_id]

    # --------------------------------------------------
    # اللعبة انتهت
    # --------------------------------------------------

    if game.get("winner"):
        return

    text = update.message.text.strip()

    # --------------------------------------------------
    # منع أوامر الإدارة
    # --------------------------------------------------

    blocked = (
        "اضف سؤال",
        "اضف لعبة",
        "حذف سؤال",
        "حذف لعبة",
        "تفعيل لعبة",
        "تعطيل لعبة",
        "تفعيل الالعاب",
        "تعطيل الالعاب",
        "الالعاب",
        "اسئلة"
    )

    if text.startswith(blocked):
        return

    # --------------------------------------------------
    # تطبيع الإجابة
    # --------------------------------------------------

    answer = text.casefold()

    correct_answers = [
        x.strip().casefold()
        for x in game.get("answers", [])
        if x and x.strip()
    ]

    # --------------------------------------------------
    # إجابة خاطئة
    # --------------------------------------------------

    if answer not in correct_answers:
        return

    # --------------------------------------------------
    # منع فوز شخصين بنفس اللحظة
    # --------------------------------------------------

    if game.get("winner"):
        return

    game["winner"] = True

    user = update.effective_user

    # ==================================================
    # إضافة النقاط
    # ==================================================

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO points
            (
                user_id,
                points
            )
            VALUES
            (
                ?,
                3
            )
            ON CONFLICT(user_id)
            DO UPDATE SET
                points = points.points + EXCLUDED.points
            """,
            (user.id,)
        )

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        game["winner"] = False

        print(
            f"❌ خطأ في إضافة نقاط اللعبة للاعب {user.id}"
        )

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # إعلان الفائز
    # --------------------------------------------------

    await update.message.reply_text(
        f"صح عليك {user.first_name} !\n"
        "✅ إجابة صحيحة\n"
        "⭐ خذيت 3 نقاط"
    )

    # --------------------------------------------------
    # إنهاء اللعبة
    # --------------------------------------------------

    active_games.pop(
        chat_id,
        None
    )


# ==================================================
# عرض أسئلة لعبة
# ==================================================

async def questions_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    game_name = update.message.text.replace(
        "اسئلة",
        ""
    ).strip()

    if not game_name:

        await update.message.reply_text(
            "❌ اكتب اسم اللعبة"
        )

        return

    _, game_questions, _ = get_games_cache()

    questions = game_questions.get(
        game_name,
        []
    )

    if not questions:

        await update.message.reply_text(
            "❌ لا توجد أسئلة"
        )

        return

    text = (
        f"❓ أسئلة لعبة {game_name}:\n\n"
    )

    for question in questions:

        text += (
            f"{question[0]} - "
            f"{question[1]}\n"
        )

    await update.message.reply_text(
        text
    )


# ==================================================
# حذف سؤال
# ==================================================

async def delete_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    text = update.message.text.replace(
        "حذف سؤال",
        ""
    ).strip()

    parts = text.rsplit(
        " ",
        1
    )

    if len(parts) != 2:

        await update.message.reply_text(
            "❌ استخدم:\n"
            "حذف سؤال اسم اللعبة رقم السؤال"
        )

        return

    game_name = parts[0]

    try:

        question_id = int(
            parts[1]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ رقم السؤال غير صحيح"
        )

        return

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM game_questions
            WHERE id=? AND game_name=?
            """,
            (
                question_id,
                game_name
            )
        )

        deleted = cur.rowcount

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    if deleted:

        await update.message.reply_text(
            "✅ تم حذف السؤال"
        )

    else:

        await update.message.reply_text(
            "❌ لم يتم العثور على السؤال"
        )


# ==================================================
# تفعيل لعبة
# ==================================================

async def enable_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    game_name = update.message.text.replace(
        "تفعيل لعبة",
        ""
    ).strip()

    if not game_name:

        await update.message.reply_text(
            "❌ اكتب اسم اللعبة"
        )

        return

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE games
            SET status='on'
            WHERE name=?
            """,
            (game_name,)
        )

        changed = cur.rowcount

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    if changed:

        await update.message.reply_text(
            f"🟢 تم تفعيل لعبة {game_name}"
        )

    else:

        await update.message.reply_text(
            "❌ اللعبة غير موجودة"
        )


# ==================================================
# تعطيل لعبة
# ==================================================

async def disable_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    game_name = update.message.text.replace(
        "تعطيل لعبة",
        ""
    ).strip()

    if not game_name:

        await update.message.reply_text(
            "❌ اكتب اسم اللعبة"
        )

        return

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE games
            SET status='off'
            WHERE name=?
            """,
            (game_name,)
        )

        changed = cur.rowcount

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    if changed:

        await update.message.reply_text(
            f"🔴 تم تعطيل لعبة {game_name}"
        )

    else:

        await update.message.reply_text(
            "❌ اللعبة غير موجودة"
        )


# ==================================================
# تفعيل كل الألعاب
# ==================================================

async def enable_all_games(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE games_settings
            SET status='on'
            WHERE id=1
            """
        )

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    await update.message.reply_text(
        "🟢 تم تفعيل جميع الألعاب"
    )


# ==================================================
# تعطيل كل الألعاب
# ==================================================

async def disable_all_games(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_game_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ ليس لديك صلاحية"
        )

        return

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE games_settings
            SET status='off'
            WHERE id=1
            """
        )

        conn.commit()

        try:
            cur.close()
        except Exception:
            pass

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        conn.close()

    # --------------------------------------------------
    # تحديث الكاش
    # --------------------------------------------------

    invalidate_games_cache()

    await update.message.reply_text(
        "🔴 تم تعطيل جميع الألعاب"
    )
