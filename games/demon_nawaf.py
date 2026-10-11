import asyncio
import json
import math
import re
from urllib.parse import quote

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from database import connect

GAME_NAME = "ديمون نواف"
MAX_QUESTIONS = 15
HTTP_TIMEOUT = 5

# traits = صفات منطقية تستخدم لاختيار الأسئلة وترتيب الشخصيات.
SEED_CHARACTERS = [
    ("neymar", "نيمار جونيور", "Neymar Jr.", "كرة القدم", "Football", "Neymar", ["male", "alive", "arabic_speaker_no", "football", "athlete", "brazilian", "famous", "real"]),
    ("ronaldo", "كريستيانو رونالدو", "Cristiano Ronaldo", "كرة القدم", "Football", "Cristiano Ronaldo", ["male", "alive", "football", "athlete", "portuguese", "famous", "real"]),
    ("messi", "ليونيل ميسي", "Lionel Messi", "كرة القدم", "Football", "Lionel Messi", ["male", "alive", "football", "athlete", "argentinian", "famous", "real"]),
    ("mbappe", "كيليان مبابي", "Kylian Mbappé", "كرة القدم", "Football", "Kylian Mbappé", ["male", "alive", "football", "athlete", "french", "famous", "real"]),
    ("salah", "محمد صلاح", "Mohamed Salah", "كرة القدم", "Football", "Mohamed Salah", ["male", "alive", "football", "athlete", "arab", "egyptian", "famous", "real"]),
    ("benzema", "كريم بنزيما", "Karim Benzema", "كرة القدم", "Football", "Karim Benzema", ["male", "alive", "football", "athlete", "arab", "french", "famous", "real"]),
    ("yasser", "ياسر القحطاني", "Yasser Al-Qahtani", "كرة القدم", "Football", "Yasser Al-Qahtani", ["male", "alive", "football", "athlete", "saudi", "arab", "famous", "real"]),
    ("salem", "سالم الدوسري", "Salem Al-Dawsari", "كرة القدم", "Football", "Salem Al-Dawsari", ["male", "alive", "football", "athlete", "saudi", "arab", "famous", "real"]),
    ("mrbeast", "مستر بيست", "MrBeast", "يوتيوبر", "YouTuber", "MrBeast", ["male", "alive", "youtuber", "american", "famous", "real"]),
    ("pewdiepie", "بيوديباي", "PewDiePie", "يوتيوبر", "YouTuber", "PewDiePie", ["male", "alive", "youtuber", "swedish", "famous", "real"]),
    ("shongx_bong", "شونق بونق", "Shongx Bong", "يوتيوبر", "YouTuber", "شونق بونق", ["male", "alive", "youtuber", "saudi", "arab", "famous", "real"]),
    ("bandarita", "بندريتا", "Bandarita", "يوتيوبر", "YouTuber", "بندريتا", ["male", "alive", "youtuber", "saudi", "arab", "famous", "real"]),
    ("aboflah", "أبو فلة", "AboFlah", "يوتيوبر", "YouTuber", "AboFlah", ["male", "alive", "youtuber", "arab", "kuwaiti", "famous", "real"]),
    ("shakira", "شاكيرا", "Shakira", "مغنية", "Singer", "Shakira", ["female", "alive", "singer", "colombian", "famous", "real"]),
    ("taylor", "تايلور سويفت", "Taylor Swift", "مغنية", "Singer", "Taylor Swift", ["female", "alive", "singer", "american", "famous", "real"]),
    ("justin", "جاستن بيبر", "Justin Bieber", "مغنٍ", "Singer", "Justin Bieber", ["male", "alive", "singer", "canadian", "famous", "real"]),
    ("jackie", "جاكي شان", "Jackie Chan", "ممثل", "Actor", "Jackie Chan", ["male", "alive", "actor", "chinese", "famous", "real"]),
    ("tomcruise", "توم كروز", "Tom Cruise", "ممثل", "Actor", "Tom Cruise", ["male", "alive", "actor", "american", "famous", "real"]),
    ("ironman", "آيرون مان", "Iron Man", "مارفل", "Marvel", "Iron Man", ["male", "fictional", "superhero", "marvel", "american", "famous"]),
    ("spiderman", "سبايدرمان", "Spider-Man", "مارفل", "Marvel", "Spider-Man", ["male", "fictional", "superhero", "marvel", "american", "famous"]),
    ("batman", "باتمان", "Batman", "دي سي", "DC", "Batman", ["male", "fictional", "superhero", "dc", "american", "famous"]),
    ("superman", "سوبرمان", "Superman", "دي سي", "DC", "Superman", ["male", "fictional", "superhero", "dc", "alien", "famous"]),
    ("naruto", "ناروتو أوزوماكي", "Naruto Uzumaki", "أنمي", "Anime", "Naruto Uzumaki", ["male", "fictional", "anime", "ninja", "japanese", "famous"]),
    ("luffy", "مونكي دي لوفي", "Monkey D. Luffy", "أنمي", "Anime", "Monkey D. Luffy", ["male", "fictional", "anime", "pirate", "japanese", "famous"]),
    ("zoro", "رورونوا زورو", "Roronoa Zoro", "أنمي", "Anime", "Roronoa Zoro", ["male", "fictional", "anime", "swordsman", "japanese", "famous"]),
    ("goku", "سون غوكو", "Son Goku", "أنمي", "Anime", "Son Goku", ["male", "fictional", "anime", "fighter", "alien", "japanese", "famous"]),
    ("levi", "ليفاي أكرمان", "Levi Ackerman", "أنمي", "Anime", "Levi Ackerman", ["male", "fictional", "anime", "soldier", "japanese", "famous"]),
    ("mikasa", "ميكاسا أكرمان", "Mikasa Ackerman", "أنمي", "Anime", "Mikasa Ackerman", ["female", "fictional", "anime", "soldier", "japanese", "famous"]),
    ("light", "لايت ياغامي", "Light Yagami", "أنمي", "Anime", "Light Yagami", ["male", "fictional", "anime", "student", "japanese", "famous"]),
    ("lelouch", "لولوش لامبيروج", "Lelouch Lamperouge", "أنمي", "Anime", "Lelouch Lamperouge", ["male", "fictional", "anime", "strategist", "japanese", "famous"]),
    ("sherlock", "شيرلوك هولمز", "Sherlock Holmes", "شخصية خيالية", "Fictional character", "Sherlock Holmes", ["male", "fictional", "detective", "british", "famous"]),
    ("harrypotter", "هاري بوتر", "Harry Potter", "شخصية خيالية", "Fictional character", "Harry Potter", ["male", "fictional", "wizard", "british", "famous"]),
    ("putin", "فلاديمير بوتين", "Vladimir Putin", "سياسة", "Politics", "Vladimir Putin", ["male", "alive", "politician", "russian", "famous", "real"]),
    ("trump", "دونالد ترامب", "Donald Trump", "سياسة", "Politics", "Donald Trump", ["male", "alive", "politician", "american", "famous", "real"]),
    ("obama", "باراك أوباما", "Barack Obama", "سياسة", "Politics", "Barack Obama", ["male", "alive", "politician", "american", "famous", "real"]),
    ("king_salman", "الملك سلمان بن عبدالعزيز", "King Salman", "شخصية سياسية", "Politics", "Salman of Saudi Arabia", ["male", "alive", "politician", "saudi", "arab", "royal", "famous", "real"]),
    ("mohammed_bin_salman", "محمد بن سلمان", "Mohammed bin Salman", "شخصية سياسية", "Politics", "Mohammed bin Salman", ["male", "alive", "politician", "saudi", "arab", "royal", "famous", "real"]),
    ("einstein", "ألبرت أينشتاين", "Albert Einstein", "عالم", "Scientist", "Albert Einstein", ["male", "deceased", "scientist", "german", "famous", "real", "historical"]),
    ("tesla", "نيكولا تسلا", "Nikola Tesla", "مخترع", "Inventor", "Nikola Tesla", ["male", "deceased", "scientist", "inventor", "serbian", "famous", "real", "historical"]),
    ("cleopatra", "كليوباترا", "Cleopatra", "شخصية تاريخية", "Historical figure", "Cleopatra", ["female", "deceased", "egyptian", "royal", "historical", "famous", "real"]),
    ("napoleon", "نابليون بونابرت", "Napoleon Bonaparte", "شخصية عسكرية", "Military figure", "Napoleon", ["male", "deceased", "military", "french", "historical", "famous", "real"]),
    ("salahuddin", "صلاح الدين الأيوبي", "Saladin", "شخصية عسكرية", "Military figure", "Saladin", ["male", "deceased", "military", "arab", "historical", "famous", "real"]),
    ("captain_america", "كابتن أمريكا", "Captain America", "مارفل", "Marvel", "Captain America", ["male", "fictional", "superhero", "marvel", "american", "famous"]),
]

QUESTION_BANK = [
    ("male", "هل الشخصية رجل؟", "Is the character male?"),
    ("female", "هل الشخصية امرأة؟", "Is the character female?"),
    ("alive", "هل الشخصية على قيد الحياة؟", "Is the character alive?"),
    ("deceased", "هل الشخصية متوفاة؟", "Is the character deceased?"),
    ("real", "هل هي شخصية حقيقية؟", "Is this a real person?"),
    ("fictional", "هل هي شخصية خيالية؟", "Is the character fictional?"),
    ("saudi", "هل هو من السعودية؟", "Is the character from Saudi Arabia?"),
    ("arab", "هل هو عربي؟", "Is the character Arab?"),
    ("american", "هل هو أمريكي؟", "Is the character American?"),
    ("football", "هل له علاقة بكرة القدم؟", "Is the character related to football/soccer?"),
    ("athlete", "هل هو رياضي؟", "Is the character an athlete?"),
    ("youtuber", "هل هو يوتيوبر أو صانع محتوى؟", "Is the character a YouTuber or content creator?"),
    ("singer", "هل هو مغنٍ أو مغنية؟", "Is the character a singer?"),
    ("actor", "هل هو ممثل؟", "Is the character an actor?"),
    ("politician", "هل هو شخصية سياسية؟", "Is the character a politician?"),
    ("military", "هل هو شخصية عسكرية؟", "Is the character a military figure?"),
    ("anime", "هل الشخصية من الأنمي؟", "Is the character from anime?"),
    ("superhero", "هل هو بطل خارق؟", "Is the character a superhero?"),
    ("marvel", "هل ينتمي إلى عالم مارفل؟", "Is the character from Marvel?"),
    ("dc", "هل ينتمي إلى عالم دي سي؟", "Is the character from DC?"),
    ("historical", "هل هي شخصية تاريخية؟", "Is the character historical?"),
    ("royal", "هل له علاقة بالعائلة الملكية؟", "Is the character royalty or related to a royal family?"),
    ("scientist", "هل هو عالم؟", "Is the character a scientist?"),
    ("detective", "هل هو محقق؟", "Is the character a detective?"),
    ("ninja", "هل هو نينجا؟", "Is the character a ninja?"),
    ("pirate", "هل هو قرصان؟", "Is the character a pirate?"),
    ("soldier", "هل هو جندي؟", "Is the character a soldier?"),
    ("wizard", "هل يستخدم السحر؟", "Does the character use magic?"),
]

ANSWERS = {
    "ar": [("yes", "ايه"), ("no", "لا"), ("unknown", "مدري"), ("probably_no", "يمكن لا"), ("probably_yes", "يمكن")],
    "en": [("yes", "Yes"), ("no", "No"), ("unknown", "Don't know"), ("probably_no", "Probably not"), ("probably_yes", "Probably")],
}

TEXT = {
    "ar": {
        "intro": "بوو 👻\nانا ديمون 🧛🏻‍♀️ اقدر اعرف مين الشخصية الي فبالك!\n\n- فكر بشخص واضغط لغتك وجاوب على اسئلتي",
        "thinking": "خلني أفكر شوي... 🧠",
        "guess": "أتوقع أن الشخصية اللي في بالك هي:\n\n**{name}**\nالفئة: {category}\n\nهل هذا هو الشخص؟",
        "correct": "كنت عارف! 👻✨\nطلعت الشخصية اللي في بالك هي **{name}**",
        "wrong": "تمام، خلني أجرب تخمين ثاني...",
        "none": "ما قدرت أوصل للشخصية بثقة 😅\nجرّب مرة ثانية وفكر بشخصية أوضح أو معروفة أكثر.",
        "question": "السؤال {n}: {question}",
        "start_private": "افتح ديمون نواف في الخاص 👻",
        "language": "اختر لغتك / Choose your language",
        "photo_error": "ما لقيت صورة مناسبة للشخصية، لكن هذا تخميني!",
    },
    "en": {
        "intro": "Boo! 👻\nI'm Demon 🧛🏻‍♀️ and I can guess the character you're thinking of!\n\n- Think of someone, choose your language, and answer my questions.",
        "thinking": "Let me think... 🧠",
        "guess": "I think the character in your mind is:\n\n**{name}**\nCategory: {category}\n\nIs this your character?",
        "correct": "I knew it! 👻✨\nThe character you had in mind was **{name}**.",
        "wrong": "Okay, let me try another guess...",
        "none": "I couldn't identify the character confidently. 😅\nTry again with a more recognizable character.",
        "question": "Question {n}: {question}",
        "start_private": "Open Demon Nawaf in private 👻",
        "language": "Choose your language / اختر لغتك",
        "photo_error": "I couldn't find a suitable image, but this is my guess!",
    },
}


def _db_execute(sql, params=(), fetch=None):
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        result = cur.fetchall() if fetch == "all" else cur.fetchone() if fetch == "one" else None
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def ensure_demon_tables():
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS demon_nawaf_characters (
                slug TEXT PRIMARY KEY,
                name_ar TEXT NOT NULL,
                name_en TEXT NOT NULL,
                category_ar TEXT NOT NULL DEFAULT 'شخصية',
                category_en TEXT NOT NULL DEFAULT 'Character',
                wiki_title TEXT NOT NULL DEFAULT '',
                traits TEXT NOT NULL DEFAULT '[]',
                image_url TEXT NOT NULL DEFAULT '',
                summary_ar TEXT NOT NULL DEFAULT '',
                summary_en TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'seed',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS demon_nawaf_sessions (
                user_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                lang TEXT NOT NULL DEFAULT 'ar',
                state TEXT NOT NULL DEFAULT 'language',
                answers TEXT NOT NULL DEFAULT '{}',
                asked TEXT NOT NULL DEFAULT '[]',
                excluded TEXT NOT NULL DEFAULT '[]',
                guesses TEXT NOT NULL DEFAULT '[]',
                question_count INTEGER NOT NULL DEFAULT 0,
                current_question TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, chat_id)
            )
        """)
        cur.execute("ALTER TABLE demon_nawaf_sessions ADD COLUMN IF NOT EXISTS current_question TEXT NOT NULL DEFAULT ''")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_demon_nawaf_session_state ON demon_nawaf_sessions(state)")
        for slug, name_ar, name_en, cat_ar, cat_en, wiki, traits in SEED_CHARACTERS:
            cur.execute("""
                INSERT INTO demon_nawaf_characters
                (slug,name_ar,name_en,category_ar,category_en,wiki_title,traits,source)
                VALUES (?,?,?,?,?,?,?,'seed')
                ON CONFLICT (slug) DO UPDATE SET
                    name_ar=EXCLUDED.name_ar, name_en=EXCLUDED.name_en,
                    category_ar=EXCLUDED.category_ar, category_en=EXCLUDED.category_en,
                    wiki_title=EXCLUDED.wiki_title, traits=EXCLUDED.traits
            """, (slug, name_ar, name_en, cat_ar, cat_en, wiki, json.dumps(traits, ensure_ascii=False)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _load_session(user_id, chat_id):
    row = _db_execute("SELECT lang,state,answers,asked,excluded,guesses,question_count,current_question FROM demon_nawaf_sessions WHERE user_id=? AND chat_id=?", (user_id, chat_id), "one")
    if not row:
        return None
    lang, state, answers, asked, excluded, guesses, count, current_question = row
    def parse(v, default):
        try:
            return json.loads(v or "")
        except Exception:
            return default
    return {"lang": lang, "state": state, "answers": parse(answers, {}), "asked": parse(asked, []), "excluded": parse(excluded, []), "guesses": parse(guesses, []), "question_count": int(count or 0), "current_question": current_question or ""}


def _save_session(user_id, chat_id, s):
    _db_execute("""
        INSERT INTO demon_nawaf_sessions
        (user_id,chat_id,lang,state,answers,asked,excluded,guesses,question_count,current_question,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,NOW())
        ON CONFLICT (user_id,chat_id) DO UPDATE SET
            lang=EXCLUDED.lang,state=EXCLUDED.state,answers=EXCLUDED.answers,
            asked=EXCLUDED.asked,excluded=EXCLUDED.excluded,guesses=EXCLUDED.guesses,
            question_count=EXCLUDED.question_count,current_question=EXCLUDED.current_question,updated_at=NOW()
    """, (user_id, chat_id, s["lang"], s["state"], json.dumps(s["answers"]), json.dumps(s["asked"]), json.dumps(s["excluded"]), json.dumps(s["guesses"]), s["question_count"], s.get("current_question", "")))


def _delete_session(user_id, chat_id):
    _db_execute("DELETE FROM demon_nawaf_sessions WHERE user_id=? AND chat_id=?", (user_id, chat_id))


def _get_characters():
    rows = _db_execute("SELECT slug,name_ar,name_en,category_ar,category_en,wiki_title,traits,image_url,summary_ar,summary_en FROM demon_nawaf_characters", (), "all") or []
    result = []
    for r in rows:
        try:
            traits = set(json.loads(r[6] or "[]"))
        except Exception:
            traits = set()
        result.append({"slug": r[0], "name_ar": r[1], "name_en": r[2], "category_ar": r[3], "category_en": r[4], "wiki_title": r[5], "traits": traits, "image_url": r[7] or "", "summary_ar": r[8] or "", "summary_en": r[9] or ""})
    return result


def _likelihood(answer, has_trait):
    # احتمالات بسيطة تسمح بإجابات غير قطعية من دون حذف الشخصية مباشرة.
    return {"yes": 0.94 if has_trait else 0.06,
            "no": 0.06 if has_trait else 0.94,
            "probably_yes": 0.72 if has_trait else 0.28,
            "probably_no": 0.28 if has_trait else 0.72,
            "unknown": 1.0}.get(answer, 1.0)


def _rank_characters(characters, answers, excluded):
    ranked = []
    for c in characters:
        if c["slug"] in excluded:
            continue
        log_score = 0.0
        for feature, answer in answers.items():
            p = _likelihood(answer, feature in c["traits"])
            log_score += math.log(max(p, 0.0001))
        ranked.append((log_score, c))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked


def _choose_question(characters, asked):
    pool = [q for q in QUESTION_BANK if q[0] not in asked]
    if not pool:
        return None
    # اختر السؤال الذي يقسم المرشحين إلى مجموعتين بأقرب حجم.
    best, best_score = None, -1
    for q in pool:
        feature = q[0]
        yes_count = sum(feature in c["traits"] for c in characters)
        no_count = len(characters) - yes_count
        if yes_count == 0 or no_count == 0:
            continue
        score = min(yes_count, no_count) / max(len(characters), 1)
        if score > best_score:
            best, best_score = q, score
    return best or pool[0]


def _language_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("العربية 🇸🇦", callback_data="dn:lang:ar")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="dn:lang:en")],
    ])


def _answer_keyboard(lang):
    labels = dict(ANSWERS[lang])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(labels["yes"], callback_data="dn:answer:yes"), InlineKeyboardButton(labels["no"], callback_data="dn:answer:no")],
        [InlineKeyboardButton(labels["unknown"], callback_data="dn:answer:unknown")],
        [InlineKeyboardButton(labels["probably_no"], callback_data="dn:answer:probably_no"), InlineKeyboardButton(labels["probably_yes"], callback_data="dn:answer:probably_yes")],
        [InlineKeyboardButton("إيقاف اللعبة" if lang == "ar" else "Stop game", callback_data="dn:stop")],
    ])


def _guess_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ايه، هو" if lang == "ar" else "Yes, that's it", callback_data="dn:guess:yes")],
        [InlineKeyboardButton("لا، مو هو" if lang == "ar" else "No, try again", callback_data="dn:guess:no")],
        [InlineKeyboardButton("إيقاف اللعبة" if lang == "ar" else "Stop game", callback_data="dn:stop")],
    ])


async def _send_next_question(update, context, user_id, chat_id, s, edit_query=None):
    lang = s["lang"]
    characters = await asyncio.to_thread(_get_characters)
    ranked = _rank_characters(characters, s["answers"], set(s["excluded"]))
    if not ranked:
        s["state"] = "finished"
        await asyncio.to_thread(_save_session, user_id, chat_id, s)
        text = TEXT[lang]["none"]
        if edit_query:
            await edit_query.edit_message_text(text)
        else:
            await update.effective_message.reply_text(text)
        await asyncio.to_thread(_delete_session, user_id, chat_id)
        return

    # بعد عدد كافٍ من الأسئلة، جرّب الشخصية الأعلى احتمالًا.
    if s["question_count"] >= 7:
        top_score, top = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else top_score - 5
        confidence_gap = top_score - second_score
        if s["question_count"] >= MAX_QUESTIONS or confidence_gap >= 1.4 or len(ranked) <= 2:
            s["state"] = "guess"
            s["guesses"] = list(dict.fromkeys(s["guesses"] + [top["slug"]]))
            await asyncio.to_thread(_save_session, user_id, chat_id, s)
            display_name = top["name_ar"] if lang == "ar" else top["name_en"]
            category = top["category_ar"] if lang == "ar" else top["category_en"]
            text = TEXT[lang]["guess"].format(name=display_name, category=category)
            markup = _guess_keyboard(lang)
            if edit_query:
                await edit_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
            else:
                await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
            return

    remaining = [c for _, c in ranked[:max(8, min(60, len(ranked)))]]
    question = _choose_question(remaining, set(s["asked"]))
    if not question:
        s["question_count"] = MAX_QUESTIONS
        await _send_next_question(update, context, user_id, chat_id, s, edit_query)
        return
    s["state"] = "question"
    s["asked"].append(question[0])
    s["current_question"] = question[0]
    await asyncio.to_thread(_save_session, user_id, chat_id, s)
    question_text = question[1] if lang == "ar" else question[2]
    body = TEXT[lang]["question"].format(n=s["question_count"] + 1, question=question_text)
    markup = _answer_keyboard(lang)
    if edit_query:
        await edit_query.edit_message_text(body, reply_markup=markup)
    else:
        await update.effective_message.reply_text(body, reply_markup=markup)


async def start_demon_nawaf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    if message.chat.type not in (ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP):
        return
    user_id, chat_id = user.id, message.chat_id
    s = {"lang": "ar", "state": "language", "answers": {}, "asked": [], "excluded": [], "guesses": [], "question_count": 0, "current_question": ""}
    await asyncio.to_thread(_save_session, user_id, chat_id, s)
    await message.reply_text(TEXT["ar"]["intro"], reply_markup=_language_keyboard())


async def demon_nawaf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return
    data = query.data or ""
    user_id, chat_id = query.from_user.id, query.message.chat_id
    s = await asyncio.to_thread(_load_session, user_id, chat_id)
    if data == "dn:stop":
        await query.answer("تم إيقاف اللعبة" if not s or s.get("lang") == "ar" else "Game stopped")
        await asyncio.to_thread(_delete_session, user_id, chat_id)
        try:
            await query.edit_message_text("انتهت اللعبة. اكتب ديمون نواف للعب مرة ثانية." if not s or s.get("lang") == "ar" else "Game stopped. Type Demon Nawaf to play again.")
        except TelegramError:
            pass
        return
    if not s:
        await query.answer("اكتب ديمون نواف لبدء لعبة جديدة" if data.endswith(":ar") or data.endswith(":en") else "Game expired", show_alert=False)
        return
    if data.startswith("dn:lang:"):
        lang = data.rsplit(":", 1)[-1]
        if lang not in ("ar", "en"):
            await query.answer()
            return
        s["lang"] = lang
        s["state"] = "question"
        await query.answer()
        await query.edit_message_text(TEXT[lang]["thinking"])
        await _send_next_question(update, context, user_id, chat_id, s, edit_query=query)
        return
    if data.startswith("dn:answer:"):
        if s.get("state") != "question":
            await query.answer("انتظر السؤال التالي" if s.get("lang") == "ar" else "Please wait for the next question")
            return
        answer = data.rsplit(":", 1)[-1]
        feature = s.get("current_question")
        if feature:
            s["answers"][feature] = answer
        s["question_count"] += 1
        await query.answer()
        await _send_next_question(update, context, user_id, chat_id, s, edit_query=query)
        return
    if data.startswith("dn:guess:"):
        choice = data.rsplit(":", 1)[-1]
        if s.get("state") != "guess":
            await query.answer()
            return
        characters = await asyncio.to_thread(_get_characters)
        ranked = _rank_characters(characters, s["answers"], set(s["excluded"]))
        if not ranked:
            await query.answer()
            await query.edit_message_text(TEXT[s["lang"]]["none"])
            await asyncio.to_thread(_delete_session, user_id, chat_id)
            return
        _, character = ranked[0]
        if choice == "no":
            s["excluded"].append(character["slug"])
            s["state"] = "question"
            await query.answer()
            await query.edit_message_text(TEXT[s["lang"]]["wrong"])
            await _send_next_question(update, context, user_id, chat_id, s, edit_query=query)
            return
        await query.answer()
        await asyncio.to_thread(_delete_session, user_id, chat_id)
        await _show_character_result(query, context, character, s["lang"])
        return
    await query.answer()


async def _wikipedia_info(title, lang):
    if not title:
        return {}
    language = "ar" if lang == "ar" else "en"
    url = f"https://{language}.wikipedia.org/w/api.php"
    headers = {"User-Agent": "DemonNawafTelegramBot/1.0 (character guessing game)"}
    def request_info():
        try:
            r = requests.get(url, params={"action": "query", "format": "json", "prop": "pageimages|extracts", "exintro": 1, "explaintext": 1, "pithumbsize": 700, "redirects": 1, "titles": title}, headers=headers, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            page = next(iter(pages.values()), {})
            return {"image": page.get("thumbnail", {}).get("source", ""), "summary": page.get("extract", ""), "title": page.get("title", title)}
        except Exception:
            return {}
    result = await asyncio.to_thread(request_info)
    if not result.get("image") and not result.get("summary"):
        def search_info():
            try:
                r = requests.get(url, params={"action": "query", "format": "json", "generator": "search", "gsrsearch": title, "gsrlimit": 1, "prop": "pageimages|extracts", "exintro": 1, "explaintext": 1, "pithumbsize": 700}, headers=headers, timeout=HTTP_TIMEOUT)
                r.raise_for_status()
                pages = r.json().get("query", {}).get("pages", {})
                page = next(iter(pages.values()), {})
                return {"image": page.get("thumbnail", {}).get("source", ""), "summary": page.get("extract", ""), "title": page.get("title", title)}
            except Exception:
                return {}
        result = await asyncio.to_thread(search_info)
    return result


async def _show_character_result(query, context, character, lang):
    name = character["name_ar"] if lang == "ar" else character["name_en"]
    category = character["category_ar"] if lang == "ar" else character["category_en"]
    wiki_title = character["wiki_title"] or character["name_en"]
    info = await _wikipedia_info(wiki_title, lang)
    image_url = character["image_url"] or info.get("image", "")
    summary = info.get("summary", "")
    if info:
        try:
            _db_execute("UPDATE demon_nawaf_characters SET image_url=CASE WHEN image_url='' THEN ? ELSE image_url END, summary_ar=CASE WHEN ?='ar' AND summary_ar='' THEN ? ELSE summary_ar END, summary_en=CASE WHEN ?='en' AND summary_en='' THEN ? ELSE summary_en END, updated_at=NOW() WHERE slug=?", (image_url, lang, summary[:2500], lang, summary[:2500], character["slug"]))
        except Exception:
            pass
    bot_username = context.application.bot_data.get("demon_nawaf_bot_username")
    if not bot_username:
        try:
            me = await context.bot.get_me()
            bot_username = me.username
            context.application.bot_data["demon_nawaf_bot_username"] = bot_username
        except TelegramError:
            bot_username = None
    buttons = []
    if bot_username:
        buttons.append([InlineKeyboardButton(TEXT[lang]["start_private"], url=f"https://t.me/{bot_username}?start=demon_nawaf")])
    if info.get("title"):
        wiki_url = f"https://{'ar' if lang == 'ar' else 'en'}.wikipedia.org/wiki/{quote(info['title'].replace(' ', '_'))}"
        buttons.append([InlineKeyboardButton("المصدر" if lang == "ar" else "Source", url=wiki_url)])
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    caption = TEXT[lang]["correct"].format(name=name) + f"\n\n{'الفئة' if lang == 'ar' else 'Category'}: {category}"
    if summary:
        caption += "\n\n" + summary[:650]
    try:
        if image_url:
            await query.message.reply_photo(photo=image_url, caption=caption[:1020], reply_markup=markup, parse_mode="Markdown")
        else:
            await query.message.reply_text(caption + "\n\n" + TEXT[lang]["photo_error"], reply_markup=markup, parse_mode="Markdown")
    except TelegramError:
        await query.message.reply_text(caption, reply_markup=markup, parse_mode="Markdown")


async def demon_nawaf_private_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Optional /start deep-link entry point: /start demon_nawaf."""
    if context.args and context.args[0] == "demon_nawaf":
        await start_demon_nawaf(update, context)
        raise ApplicationHandlerStop
