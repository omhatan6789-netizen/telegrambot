from telegram import Update
from telegram.ext import ContextTypes
active_games = {}
from database import connect

import random

OWNER_ID = 8453977662


# =====================
# الصلاحيات
# =====================

async def is_game_admin(user_id):

    if user_id == OWNER_ID:
        return True


    conn = connect()
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

    conn.close()


    if not data:
        return False


    return data[0] in [
        " نائب المالك",
        "ادمن اساسي",
        "ادمن"
    ]



# =====================
# جلسة إضافة لعبة
# =====================

add_game_sessions = {}



# =====================
# بدء إضافة لعبة
# =====================

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



    # إغلاق الجلسات الأخرى

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


    except:
        pass



    add_game_sessions[user_id] = {
        "step": "name"
    }



    await update.message.reply_text(
        "حسنًا، أرسل اسم اللعبة التي تريد إضافتها"
    )




# =====================
# استقبال اسم اللعبة
# =====================

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



    # منع حفظ الأوامر كلعبة

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



    conn = connect()
    cur = conn.cursor()



    cur.execute(
        """
        SELECT name
        FROM games
        WHERE name=?
        """,
        (game_name,)
    )


    exists = cur.fetchone()



    if exists:

        conn.close()

        del add_game_sessions[user_id]


        await update.message.reply_text(
            "❌ اللعبة موجودة مسبقًا"
        )

        return



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
    conn.close()



    del add_game_sessions[user_id]



    await update.message.reply_text(
        f"✅ تم إضافة اللعبة: {game_name}\n\n"
        f"لإضافة أسئلة استخدم:\n"
        f"اضف سؤال {game_name}"
    )


    # =====================
# جلسة إضافة سؤال
# =====================

add_question_sessions = {}


# =====================
# عرض الألعاب
# الأمر:
# الالعاب
# =====================

async def games_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        SELECT name, status
        FROM games
        ORDER BY name
        """
    )


    games = cur.fetchall()


    conn.close()



    if not games:

        await update.message.reply_text(
            "❌ لا توجد ألعاب مضافة"
        )

        return



    text = "🎮 الألعاب الموجودة:\n\n"



    for game in games:

        status = "🟢" if game[1] == "on" else "🔴"

        text += (
            f"{status} {game[0]}\n"
        )



    await update.message.reply_text(
        text
    )



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
    conn.close()



    await update.message.reply_text(
        f"✅ تم حذف اللعبة: {name}"
    )



# =====================
# بدء إضافة سؤال
# الأمر:
# اضف سؤال اسم اللعبة
# =====================

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



    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        SELECT name
        FROM games
        WHERE name=?
        """,
        (game_name,)
    )


    game = cur.fetchone()


    conn.close()



    if not game:

        await update.message.reply_text(
            "❌ اللعبة غير موجودة"
        )

        return



    # إنشاء جلسة إضافة سؤال
    add_question_sessions[user_id] = {

        "game": game_name,

        "step": "question",

        "answers": [],

        # تجاهل نفس رسالة الأمر
        "ignore_next": True
    }



    await update.message.reply_text(
        f"✅ جاري إضافة سؤال للعبة: {game_name}\n\n"
        "📩 أرسل السؤال الآن.\n"
        "يمكنك إرسال:\n"
        "- نص فقط\n"
        "- أو صورة مع كابشن."
    )


# =====================
# استقبال السؤال والإجابات
# =====================

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


    # تجاهل نفس رسالة: اضف سؤال تفكيك
    if session.get("ignore_next"):
        session["ignore_next"] = False
        return



    # استقبال السؤال

    if session["step"] == "question":

        image = None
        caption = None


        if update.message.photo:

            image = update.message.photo[-1].file_id

            caption = update.message.caption

            question = caption if caption else "ما الإجابة؟"



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




    # استقبال الإجابات

    if session["step"] == "answers":


        if not update.message.text:
            return


        text = update.message.text.strip()



        if text == "تم":


            if not session["answers"]:

                await update.message.reply_text(
                    "❌ أضف إجابة واحدة على الأقل."
                )

                return



            conn = connect()

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
                    "|".join(session["answers"])
                )
            )



            conn.commit()

            conn.close()



            del add_question_sessions[user_id]



            await update.message.reply_text(
                "✅ تم حفظ السؤال بنجاح."
            )

            return



        session["answers"].append(text)



        await update.message.reply_text(
            "✅ تمت إضافة الإجابة."
        )



# =====================
# تشغيل اللعبة
# =====================

async def play_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    if not update.message.text:
        return


    text = update.message.text.strip()


    # منع أمر إضافة سؤال من الدخول للألعاب
    if text.startswith("اضف سؤال"):
        return


    # منع أوامر الإدارة
    blocked = [
        "اضف لعبة",
        "حذف سؤال",
        "حذف لعبة",
        "تفعيل لعبة",
        "تعطيل لعبة",
        "تفعيل الالعاب",
        "تعطيل الالعاب",
        "الالعاب",
        "اسئلة"
    ]


    for cmd in blocked:
        if text.startswith(cmd):
            return



    game_name = text



    global active_games

    if "active_games" not in globals():
        active_games = {}



    conn = connect()
    cur = conn.cursor()



    # فحص حالة جميع الألعاب

    cur.execute(
        """
        SELECT status
        FROM games_settings
        WHERE id=1
        """
    )

    settings = cur.fetchone()



    if settings and settings[0] == "off":

        conn.close()
        return



    # البحث عن اللعبة

    cur.execute(
        """
        SELECT status
        FROM games
        WHERE name=?
        """,
        (game_name,)
    )


    game = cur.fetchone()



    if not game:

        conn.close()
        return



    if game[0] == "off":

        conn.close()

        await update.message.reply_text(
            "❌ هذه اللعبة معطلة"
        )

        return



    # جلب الأسئلة

    cur.execute(
        """
        SELECT
        id,
        question,
        image,
        caption,
        answers

        FROM game_questions

        WHERE game_name=?

        """,
        (game_name,)
    )


    questions = cur.fetchall()



    conn.close()



    if not questions:

        await update.message.reply_text(
            "❌ لا توجد أسئلة لهذه اللعبة"
        )

        return



    question = random.choice(
        questions
    )



    active_games[
        update.effective_chat.id
    ] = {

        "answers":
        [
            x.strip().lower()
            for x in question[4].split("|")
        ],

        "winner": False,

        "game": game_name

    }



    text = (
        
        f"❓ {question[1]}\n\n"
        "أول واحد يجاوب ياخذ\n"
        "⭐ +3 نقاط"
    )



    if question[2]:

        await update.message.reply_photo(
            photo=question[2],
            caption=text
        )

    else:

        await update.message.reply_text(
            text
        )





# =====================
# فحص الإجابات
# =====================

async def check_game_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    if not update.message.text:
        return



    user_id = update.effective_user.id



    # إذا كان المستخدم يضيف سؤال لا تحسب الإجابة
    if user_id in add_question_sessions:
        return



    text = update.message.text.strip()



    blocked = [
        "اضف سؤال",
        "اضف لعبة",
        "حذف سؤال",
        "حذف لعبة",
        "تفعيل لعبة",
        "تعطيل لعبة",
        "الالعاب",
        "اسئلة"
    ]



    for cmd in blocked:
        if text.startswith(cmd):
            return



    chat_id = update.effective_chat.id



    global active_games


    if "active_games" not in globals():
        active_games = {}



    if chat_id not in active_games:
        return



    game = active_games[chat_id]



    if game.get("winner"):
        return



    answer = text.lower()



    if answer not in game["answers"]:
        return



    game["winner"] = True



    user = update.effective_user



    conn = connect()
    cur = conn.cursor()



    cur.execute(
        """
        INSERT INTO points
        (
            user_id,
            points
        )

        VALUES
        (?, 3)

        ON CONFLICT(user_id)

        DO UPDATE SET
        points = points + EXCLUDED.points
        """,
        (user.id,)
    )



    conn.commit()
    conn.close()



    await update.message.reply_text(
        f" !صح عليك {user.first_name}\n"
        "✅ إجابة صحيحة\n"
        " خذيت 3 نقاط🌟"
    )



    del active_games[chat_id]



# =====================
# عرض أسئلة لعبة
# الأمر:
# اسئلة اسم اللعبة
# =====================

async def questions_list(
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



    game_name = update.message.text.replace(
        "اسئلة",
        ""
    ).strip()



    if not game_name:

        await update.message.reply_text(
            "❌ اكتب اسم اللعبة"
        )

        return



    conn = connect()
    cur = conn.cursor()



    cur.execute(
        """
        SELECT id, question
        FROM game_questions
        WHERE game_name=?
        """,
        (game_name,)
    )


    questions = cur.fetchall()


    conn.close()



    if not questions:

        await update.message.reply_text(
            "❌ لا توجد أسئلة"
        )

        return



    text = (
        f"❓ أسئلة لعبة {game_name}:\n\n"
    )



    for q in questions:

        text += (
            f"{q[0]} - {q[1]}\n"
        )



    await update.message.reply_text(
        text
    )




# =====================
# حذف سؤال
# الأمر:
# حذف سؤال اسم اللعبة رقم
# مثال:
# حذف سؤال تفكيك 5
# =====================

async def delete_question(
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

        question_id = int(parts[1])

    except:


        await update.message.reply_text(
            "❌ رقم السؤال غير صحيح"
        )

        return



    conn = connect()
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
    conn.close()



    if deleted:

        await update.message.reply_text(
            "✅ تم حذف السؤال"
        )

    else:

        await update.message.reply_text(
            "❌ لم يتم العثور على السؤال"
        )



      # =====================
# تفعيل لعبة
# الأمر:
# تفعيل لعبة اسم اللعبة
# =====================

async def enable_game(
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
    conn.close()



    if changed:

        await update.message.reply_text(
            f"🟢 تم تفعيل لعبة {game_name}"
        )

    else:

        await update.message.reply_text(
            "❌ اللعبة غير موجودة"
        )




# =====================
# تعطيل لعبة
# =====================

async def disable_game(
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
    conn.close()



    if changed:

        await update.message.reply_text(
            f"🔴 تم تعطيل لعبة {game_name}"
        )

    else:

        await update.message.reply_text(
            "❌ اللعبة غير موجودة"
        )




# =====================
# تفعيل كل الألعاب
# =====================

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
    cur = conn.cursor()



    cur.execute(
        """
        UPDATE games_settings
        SET status='on'
        WHERE id=1
        """
    )



    conn.commit()
    conn.close()



    await update.message.reply_text(
        "🟢 تم تفعيل جميع الألعاب"
    )




# =====================
# تعطيل كل الألعاب
# =====================

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
    cur = conn.cursor()



    cur.execute(
        """
        UPDATE games_settings
        SET status='off'
        WHERE id=1
        """
    )



    conn.commit()
    conn.close()



    await update.message.reply_text(
        "🔴 تم تعطيل جميع الألعاب"
    )  