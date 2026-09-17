import asyncio
import io
import json
import os
import random
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List

from PIL import Image

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes, filters


# =========================================================
# الإعدادات
# =========================================================

GAME_NAME = "توقع الصورة"

MIN_PLAYERS = 2

MIN_TARGET_POINTS = 5
MAX_TARGET_POINTS = 15

# نقاط البوت الأصلية حسب سرعة الإجابة
ROUND_FIRST_REWARD = 60       # 0 - 20
ROUND_SECOND_REWARD = 45      # 20 - 40
ROUND_THIRD_REWARD = 30       # 40 - 60
ROUND_FINAL_REWARD = 15       # آخر 5 ثواني

REVEAL_INTERVAL = 20
FINAL_GUESS_SECONDS = 5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")


# =========================================================
# الاستيرادات الاختيارية
# =========================================================

try:
    from permissions import get_permission_level
except Exception:
    get_permission_level = None


try:
    from handlers.roles import (
        is_primary_developer,
        is_secondary_developer,
        get_rank,
    )
except Exception:
    is_primary_developer = None
    is_secondary_developer = None
    get_rank = None


try:
    from handlers.points import add_points
except Exception:
    add_points = None


# =========================================================
# بيانات اللاعب
# =========================================================

@dataclass
class ImagePlayer:
    user_id: int
    name: str

    # نقاط لعبة توقع الصورة
    game_points: int = 0

    # نقاط البوت الأصلية المكتسبة داخل هذه اللعبة
    original_points: int = 0


# =========================================================
# حالة اللعبة
# =========================================================

@dataclass
class ImageQuizState:
    chat_id: int

    # الشخص الذي أنشأ القيم
    host_id: int
    host_name: str

    # اللاعبين الموجودين حاليًا في القيم
    players: Dict[int, ImagePlayer] = field(default_factory=dict)

    # الأشخاص الذين خرجوا من القيم
    eliminated_players: Set[int] = field(default_factory=set)

    # النقاط المطلوبة للفوز
    target_points: Optional[int] = None

    started: bool = False
    finished: bool = False

    # رقم الجولة
    current_round: int = 0

    # السؤال الحالي
    current_question: Optional[dict] = None

    # الرسائل
    board_message_id: Optional[int] = None
    image_message_id: Optional[int] = None
    result_message_id: Optional[int] = None

    # حالة الجولة
    waiting_continue: bool = False
    answer_locked: bool = False

    round_started_at: Optional[float] = None

    # 0 = بداية
    # 1 = بعد 20 ثانية
    # 2 = بعد 40 ثانية
    # 3 = الصورة كاملة
    reveal_stage: int = 0

    final_guess_phase: bool = False

    # مؤقت الجولة
    round_task: Optional[asyncio.Task] = None

    # الأسئلة المستخدمة
    used_question_ids: Set[str] = field(default_factory=set)


# =========================================================
# الألعاب النشطة
# =========================================================

IMAGE_QUIZZES: Dict[int, ImageQuizState] = {}


# =========================================================
# الصلاحيات
# =========================================================

def _get_rank_level(user_id: int) -> int:
    """
    يحاول معرفة مستوى رتبة المستخدم من نظام المشروع الحالي.
    """

    # المطور الأساسي
    try:
        if is_primary_developer and is_primary_developer(user_id):
            return 6
    except Exception:
        pass

    # المطور المساعد
    try:
        if is_secondary_developer and is_secondary_developer(user_id):
            return 6
    except Exception:
        pass

    # نظام الصلاحيات
    try:
        if get_permission_level:
            level = get_permission_level(user_id)

            # إذا كانت الدالة async لا نستطيع انتظارها هنا
            if asyncio.iscoroutine(level):
                level = None

            if isinstance(level, int):
                return level
    except Exception:
        pass

    # نظام الرتب
    try:
        if get_rank:
            rank = get_rank(user_id)

            if isinstance(rank, int):
                return rank

            if isinstance(rank, str):
                ranks = {
                    "عضو": 0,
                    "مميز": 1,
                    "ادمن": 2,
                    "ادمن اساسي": 3,
                    "نائب المالك": 4,
                    "المالك": 5,
                    "Dev": 6,
                    "dev": 6,
                }

                return ranks.get(rank.strip(), 0)
    except Exception:
        pass

    return 0


def _is_admin(user_id: int) -> bool:
    return _get_rank_level(user_id) >= 2


# =========================================================
# التأكد من القروب
# =========================================================

async def _ensure_group(update: Update) -> bool:
    chat = update.effective_chat

    if not chat:
        return False

    if chat.type not in ("group", "supergroup"):
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ هذا الأمر يعمل داخل القروبات فقط."
            )
        return False

    return True


# =========================================================
# اسم اللاعب
# =========================================================

def _player_name(user) -> str:
    if user.first_name:
        return user.first_name

    if user.username:
        return f"@{user.username}"

    return str(user.id)


# =========================================================
# تنظيف الإجابات
# =========================================================

def _normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.strip().lower()

    # إزالة التشكيل
    text = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )

    # توحيد بعض الحروف العربية
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # إزالة التطويل
    text = text.replace("ـ", "")

    # إزالة الرموز وعلامات الترقيم
    text = re.sub(r"[^\w\s]", " ", text)

    # توحيد المسافات
    text = re.sub(r"\s+", " ", text).strip()

    return text


# =========================================================
# استخراج إجابات السؤال
# =========================================================

def _question_answers(question: dict) -> List[str]:
    answers = []

    answer = question.get("answer")

    if isinstance(answer, str) and answer.strip():
        answers.append(answer)

    alternatives = question.get("alternative_answers", [])

    if isinstance(alternatives, str):
        alternatives = [alternatives]

    if isinstance(alternatives, list):
        for item in alternatives:
            if isinstance(item, str) and item.strip():
                answers.append(item)

    # إزالة التكرار بعد التطبيع
    result = []
    seen = set()

    for answer_text in answers:
        normalized = _normalize_text(answer_text)

        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


# =========================================================
# تحميل الأسئلة
# =========================================================

def load_questions() -> List[dict]:
    if not os.path.exists(QUESTIONS_FILE):
        return []

    try:
        with open(
            QUESTIONS_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            questions = data.get("questions", [])

            if isinstance(questions, list):
                return questions

    except Exception as e:
        print(f"[IMAGE QUIZ] Error loading questions: {e}")

    return []


# =========================================================
# اختيار سؤال
# =========================================================

def choose_question(state: ImageQuizState) -> Optional[dict]:
    questions = load_questions()

    if not questions:
        return None

    available = []

    for question in questions:
        question_id = str(question.get("id", ""))

        if question_id not in state.used_question_ids:
            available.append(question)

    # إذا انتهت جميع الأسئلة نعيد استخدام الأسئلة
    if not available:
        state.used_question_ids.clear()
        available = questions.copy()

    if not available:
        return None

    question = random.choice(available)

    question_id = str(question.get("id", ""))

    if question_id:
        state.used_question_ids.add(question_id)

    return question


# =========================================================
# مسار الصورة
# =========================================================

def _get_image_path(image_path: str) -> str:
    if not image_path:
        return ""

    image_path = image_path.strip()

    if os.path.isabs(image_path):
        return image_path

    return os.path.join(BASE_DIR, image_path)


# =========================================================
# قص الصورة حسب المرحلة
# =========================================================

def _crop_zoom_image(
    image_path: str,
    stage: int
) -> Optional[io.BytesIO]:

    if not os.path.exists(image_path):
        return None

    try:
        image = Image.open(image_path)

        # تحويل للصورة العادية
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, "white")
            background.paste(
                image,
                mask=image.getchannel("A")
            )
            image = background
        else:
            image = image.convert("RGB")

        width, height = image.size

        # كل مرحلة تظهر مساحة أكبر من الصورة
        crop_ratios = {
            0: 0.30,
            1: 0.52,
            2: 0.72,
            3: 1.00,
        }

        ratio = crop_ratios.get(stage, 1.00)

        if ratio < 1.0:
            crop_width = int(width * ratio)
            crop_height = int(height * ratio)

            left = max(0, (width - crop_width) // 2)
            top = max(0, (height - crop_height) // 2)

            right = min(width, left + crop_width)
            bottom = min(height, top + crop_height)

            image = image.crop(
                (left, top, right, bottom)
            )

        # الحجم المناسب لتيليجرام
        image.thumbnail(
            (1280, 1280),
            Image.Resampling.LANCZOS
        )

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True
        )

        output.seek(0)

        return output

    except Exception as e:
        print(f"[IMAGE QUIZ] Image processing error: {e}")
        return None


# =========================================================
# نص مرحلة الصورة
# =========================================================

def _stage_text(state: ImageQuizState) -> str:
    if state.reveal_stage == 0:
        return "🔎 الصورة مخفية بشكل كبير"

    if state.reveal_stage == 1:
        return "👀 بدأت الصورة تتضح"

    if state.reveal_stage == 2:
        return "👁️ الصورة أصبحت أوضح"

    return "🖼️ الصورة كاملة"


# =========================================================
# إرسال / تعديل الصورة
# =========================================================

async def _send_or_edit_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState
):
    if not state.current_question:
        return

    image_path = state.current_question.get("image")

    if not image_path:
        return

    image_path = _get_image_path(image_path)

    image_data = _crop_zoom_image(
        image_path,
        state.reveal_stage
    )

    if image_data is None:
        await update.effective_chat.send_message(
            "❌ تعذر تحميل صورة الجولة."
        )
        return

    elapsed_text = ""

    if state.reveal_stage == 0:
        elapsed_text = "⏱️ الوقت: 0 - 20 ثانية"
    elif state.reveal_stage == 1:
        elapsed_text = "⏱️ الوقت: 20 - 40 ثانية"
    elif state.reveal_stage == 2:
        elapsed_text = "⏱️ الوقت: 40 - 60 ثانية"
    else:
        elapsed_text = "⏱️ آخر 5 ثواني"

    caption = (
        f"🖼️ *الجولة {state.current_round}*\n\n"
        f"{_stage_text(state)}\n"
        f"{elapsed_text}\n\n"
        f"🎯 كل إجابة صحيحة = +1 نقطة"
    )

    # إذا كانت هناك رسالة صورة سابقة نحاول تعديلها
    if state.image_message_id:

        try:
            media = InputMediaPhoto(
                media=image_data,
                caption=caption,
                parse_mode="Markdown"
            )

            await context.bot.edit_message_media(
                chat_id=state.chat_id,
                message_id=state.image_message_id,
                media=media
            )

            return

        except Exception as e:
            print(
                f"[IMAGE QUIZ] Failed to edit image: {e}"
            )

    # إرسال صورة جديدة
    message = await update.effective_chat.send_photo(
        photo=image_data,
        caption=caption,
        parse_mode="Markdown"
    )

    state.image_message_id = message.message_id


# =========================================================
# لوحة اللاعبين
# =========================================================

async def _update_board(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState
):
    if not state.board_message_id:
        return

    players = list(state.players.values())

    players.sort(
        key=lambda p: (
            p.game_points,
            p.original_points
        ),
        reverse=True
    )

    lines = [
        "🖼️ *توقع الصورة*",
        ""
    ]

    if state.target_points:
        lines.append(
            f"🎯 الهدف: *{state.target_points} نقاط*"
        )
        lines.append("")

    if not players:
        lines.append("👥 لا يوجد لاعبين.")
    else:
        for index, player in enumerate(players, start=1):
            lines.append(
                f"{index}. {player.name} — "
                f"*{player.game_points}* نقطة"
            )

    lines.append("")

    if not state.started:
        lines.append("⏳ بانتظار بدء القيم…")
    elif state.waiting_continue:
        lines.append(
            "⏸️ الجولة انتهت.\n"
            "الأدمن يكتب `.كمل` للجولة التالية."
        )
    elif state.final_guess_phase:
        lines.append(
            "⏰ الصورة كاملة!\n"
            "لديكم 5 ثوانٍ للإجابة."
        )
    else:
        lines.append("🎮 الجولة جارية…")

    try:
        await context.bot.edit_message_text(
            chat_id=state.chat_id,
            message_id=state.board_message_id,
            text="\n".join(lines),
            parse_mode="Markdown"
        )
    except Exception:
        pass


# =========================================================
# بدء الجولة
# =========================================================

async def start_round(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState
):
    if state.finished:
        return

    if len(state.players) < MIN_PLAYERS:
        state.waiting_continue = True

        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                "❌ لا يمكن بدء الجولة.\n"
                f"يجب أن يكون عدد اللاعبين {MIN_PLAYERS} على الأقل."
            )
        )

        return

    question = choose_question(state)

    if not question:
        state.waiting_continue = True

        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                "❌ لا توجد أسئلة في مكتبة الصور.\n\n"
                "تأكد من وجود ملف `questions.json`."
            ),
            parse_mode="Markdown"
        )

        return

    state.current_question = question
    state.current_round += 1

    state.answer_locked = False
    state.waiting_continue = False

    state.round_started_at = asyncio.get_running_loop().time()

    state.reveal_stage = 0
    state.final_guess_phase = False

    # نرسل/نحدث اللوحة
    await _update_board(
        context,
        state
    )

    # الصورة الأولى
    fake_update = Update(
        update_id=0,
        message=None
    )

    # لا نستخدم fake_update فعليًا
    image_path = question.get("image")

    if image_path:
        image_path = _get_image_path(image_path)

        image_data = _crop_zoom_image(
            image_path,
            0
        )

        if image_data:
            caption = (
                f"🖼️ *الجولة {state.current_round}*\n\n"
                "🔎 الصورة مخفية بشكل كبير\n"
                "⏱️ الوقت: 0 - 20 ثانية\n\n"
                "🎯 كل إجابة صحيحة = +1 نقطة"
            )

            try:
                message = await context.bot.send_photo(
                    chat_id=state.chat_id,
                    photo=image_data,
                    caption=caption,
                    parse_mode="Markdown"
                )

                state.image_message_id = message.message_id

            except Exception as e:
                print(
                    f"[IMAGE QUIZ] Failed sending first image: {e}"
                )

    # رسالة بداية الجولة
    await context.bot.send_message(
        chat_id=state.chat_id,
        text=(
            f"🎮 *الجولة {state.current_round} بدأت!*\n\n"
            "🖼️ حاول معرفة الصورة.\n"
            "⚡ كل إجابة صحيحة = +1 نقطة في القيم.\n\n"
            "💰 نقاط البوت الأصلية:\n"
            "• 0 - 20 ثانية: +60\n"
            "• 20 - 40 ثانية: +45\n"
            "• 40 - 60 ثانية: +30\n"
            "• آخر 5 ثواني: +15"
        ),
        parse_mode="Markdown"
    )

    # إلغاء أي مؤقت سابق
    if state.round_task and not state.round_task.done():
        state.round_task.cancel()

    state.round_task = asyncio.create_task(
        run_round_timer(
            context,
            state
        )
    )


# =========================================================
# مؤقت الجولة
# =========================================================

async def run_round_timer(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState
):
    try:
        # -------------------------------------------------
        # 20 ثانية
        # -------------------------------------------------

        await asyncio.sleep(20)

        if state.finished or state.answer_locked:
            return

        state.reveal_stage = 1

        await _update_round_image(
            context,
            state
        )

        # -------------------------------------------------
        # 40 ثانية
        # -------------------------------------------------

        await asyncio.sleep(20)

        if state.finished or state.answer_locked:
            return

        state.reveal_stage = 2

        await _update_round_image(
            context,
            state
        )

        # -------------------------------------------------
        # 60 ثانية
        # -------------------------------------------------

        await asyncio.sleep(20)

        if state.finished or state.answer_locked:
            return

        state.reveal_stage = 3
        state.final_guess_phase = True

        await _update_round_image(
            context,
            state
        )

        await _update_board(
            context,
            state
        )

        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                "⏰ *انتهت الـ60 ثانية!*\n\n"
                "🖼️ الصورة كاملة الآن.\n"
                "⚡ أمامكم *5 ثوانٍ* للإجابة.\n"
                "🎯 الإجابة الصحيحة الآن = +1 نقطة\n"
                "💰 وتحصل على +15 نقطة أصلية."
            ),
            parse_mode="Markdown"
        )

        # -------------------------------------------------
        # آخر 5 ثواني
        # -------------------------------------------------

        await asyncio.sleep(FINAL_GUESS_SECONDS)

        if state.finished or state.answer_locked:
            return

        await finish_round_without_answer(
            context,
            state
        )

    except asyncio.CancelledError:
        return

    except Exception as e:
        print(
            f"[IMAGE QUIZ] Timer error: {e}"
        )


# =========================================================
# تحديث صورة الجولة
# =========================================================

async def _update_round_image(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState
):
    if not state.current_question:
        return

    image_path = state.current_question.get("image")

    if not image_path:
        return

    image_path = _get_image_path(image_path)

    image_data = _crop_zoom_image(
        image_path,
        state.reveal_stage
    )

    if image_data is None:
        return

    if state.reveal_stage == 1:
        caption = (
            f"🖼️ *الجولة {state.current_round}*\n\n"
            "👀 الصورة أصبحت أوضح\n"
            "⏱️ 20 - 40 ثانية\n\n"
            "🎯 كل إجابة صحيحة = +1 نقطة"
        )

    elif state.reveal_stage == 2:
        caption = (
            f"🖼️ *الجولة {state.current_round}*\n\n"
            "👁️ الصورة أصبحت أوضح أكثر\n"
            "⏱️ 40 - 60 ثانية\n\n"
            "🎯 كل إجابة صحيحة = +1 نقطة"
        )

    else:
        caption = (
            f"🖼️ *الجولة {state.current_round}*\n\n"
            "🖼️ الصورة كاملة\n"
            "⏰ آخر 5 ثواني!\n\n"
            "🎯 كل إجابة صحيحة = +1 نقطة\n"
            "💰 المكافأة الأصلية: +15"
        )

    try:
        if state.image_message_id:

            media = InputMediaPhoto(
                media=image_data,
                caption=caption,
                parse_mode="Markdown"
            )

            await context.bot.edit_message_media(
                chat_id=state.chat_id,
                message_id=state.image_message_id,
                media=media
            )

        else:

            message = await context.bot.send_photo(
                chat_id=state.chat_id,
                photo=image_data,
                caption=caption,
                parse_mode="Markdown"
            )

            state.image_message_id = message.message_id

    except Exception as e:
        print(
            f"[IMAGE QUIZ] Failed updating image: {e}"
        )


# =========================================================
# نهاية الجولة بدون إجابة
# =========================================================

async def finish_round_without_answer(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState
):
    state.answer_locked = True
    state.final_guess_phase = False
    state.waiting_continue = True

    if state.round_task:
        current_task = asyncio.current_task()

        if state.round_task != current_task:
            try:
                state.round_task.cancel()
            except Exception:
                pass

    question = state.current_question

    answer = "غير معروف"

    if question:
        answer = question.get(
            "answer",
            "غير معروف"
        )

    await context.bot.send_message(
        chat_id=state.chat_id,
        text=(
            f"⏱️ *انتهت الجولة {state.current_round}!*\n\n"
            f"❌ لم يجب أحد بشكل صحيح.\n\n"
            f"✅ الإجابة: *{answer}*\n\n"
            "⏸️ الأدمن يكتب `.كمل` للجولة التالية."
        ),
        parse_mode="Markdown"
    )

    await _update_board(
        context,
        state
    )


# =========================================================
# إضافة نقاط البوت الأصلية
# =========================================================

async def _give_original_points(
    user_id: int,
    points: int
):
    if points <= 0:
        return

    if not add_points:
        return

    try:
        result = add_points(
            user_id,
            points
        )

        if asyncio.iscoroutine(result):
            await result

    except TypeError:
        try:
            result = add_points(
                user_id=user_id,
                amount=points
            )

            if asyncio.iscoroutine(result):
                await result

        except Exception as e:
            print(
                f"[IMAGE QUIZ] Failed adding points: {e}"
            )

    except Exception as e:
        print(
            f"[IMAGE QUIZ] Failed adding points: {e}"
        )


# =========================================================
# حساب مكافأة الإجابة
# =========================================================

def _get_original_reward(elapsed: float) -> int:
    if elapsed < 20:
        return ROUND_FIRST_REWARD

    if elapsed < 40:
        return ROUND_SECOND_REWARD

    if elapsed < 60:
        return ROUND_THIRD_REWARD

    return ROUND_FINAL_REWARD


# =========================================================
# فحص إجابة اللاعب
# =========================================================

async def check_image_quiz_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in ("group", "supergroup"):
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    if not state.started:
        return

    if state.finished:
        return

    if state.answer_locked:
        return

    if user.id not in state.players:
        return

    if not message.text:
        return

    text = message.text.strip()

    # لا نعتبر أوامر اللعبة إجابات
    ignored_commands = {
        "دخول",
        "خروج",
        ".اضافة",
        ".اعدادات",
        ".ابدا",
        ".كمل",
        ".انهاء",
        "توقع الصورة",
    }

    if text in ignored_commands:
        return

    # لا نعالج النصوص الفارغة
    normalized_text = _normalize_text(text)

    if not normalized_text:
        return

    if not state.current_question:
        return

    correct_answers = _question_answers(
        state.current_question
    )

    if normalized_text not in correct_answers:
        return

    # قفل الجولة مباشرة
    state.answer_locked = True
    state.final_guess_phase = False

    # إلغاء المؤقت
    if state.round_task:
        try:
            state.round_task.cancel()
        except Exception:
            pass

    # حساب الوقت
    now = asyncio.get_running_loop().time()

    if state.round_started_at:
        elapsed = now - state.round_started_at
    else:
        elapsed = 0

    reward = _get_original_reward(elapsed)

    player = state.players.get(user.id)

    if not player:
        state.answer_locked = False
        return

    # +1 في نقاط اللعبة
    player.game_points += 1

    # النقاط الأصلية منفصلة
    player.original_points += reward

    answer = state.current_question.get(
        "answer",
        text
    )

    # معرفة إذا وصل اللاعب للهدف
    target_reached = (
        state.target_points is not None
        and player.game_points >= state.target_points
    )

    if target_reached:

        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"🎉 *إجابة صحيحة!*\n\n"
                f"👤 اللاعب: *{player.name}*\n"
                f"✅ الإجابة: *{answer}*\n\n"
                f"🎯 +1 نقطة في القيم\n"
                f"💰 +{reward} نقطة أصلية\n\n"
                f"🏆 وصل إلى الهدف "
                f"*{state.target_points} نقاط*!"
            ),
            parse_mode="Markdown"
        )

        await finish_image_quiz(
            context,
            state,
            winner_id=user.id
        )

        return

    # إجابة صحيحة عادية
    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            f"🎯 *إجابة صحيحة!*\n\n"
            f"👤 {player.name}\n"
            f"✅ {answer}\n\n"
            f"🏅 +1 نقطة في القيم\n"
            f"💰 +{reward} نقطة أصلية\n\n"
            f"📊 نقاطه الآن: *{player.game_points}*"
        ),
        parse_mode="Markdown"
    )

    state.waiting_continue = True

    await _update_board(
        context,
        state
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            "⏸️ انتهت الجولة.\n"
            "الأدمن يكتب `.كمل` للجولة التالية."
        )
    )


# =========================================================
# بدء اللعبة
# =========================================================

async def start_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    # يجب أن يكون منشئ القيم أدمن
    if not _is_admin(user.id):
        await message.reply_text(
            "❌ لازم تكون أدمن لإنشاء لعبة توقع الصورة."
        )
        return

    if chat.id in IMAGE_QUIZZES:
        await message.reply_text(
            "⚠️ توجد لعبة توقع الصورة بالفعل في هذا القروب."
        )
        return

    state = ImageQuizState(
        chat_id=chat.id,
        host_id=user.id,
        host_name=_player_name(user)
    )

    IMAGE_QUIZZES[chat.id] = state

    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 اختيار النقاط",
                callback_data="iq:settings"
            )
        ]
    ]

    board = await message.reply_text(
        (
            "🖼️ *توقع الصورة*\n\n"
            f"👑 المنظم: *{state.host_name}*\n\n"
            "👥 يجب دخول لاعبين على الأقل.\n"
            "🎯 حددوا نقاط الفوز من زر الإعدادات.\n\n"
            "اكتب `دخول` للانضمام."
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    state.board_message_id = board.message_id


# =========================================================
# دخول لاعب
# =========================================================

async def join_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    # بعد بداية اللعبة دخول عادي ممنوع
    if state.started:
        await message.reply_text(
            "❌ القيم بدأ بالفعل.\n"
            "إذا تبي تضيف شخص استخدم `.اضافة`."
        )
        return

    if user.id in state.players:
        await message.reply_text(
            "⚠️ أنت داخل القيم بالفعل."
        )
        return

    state.players[user.id] = ImagePlayer(
        user_id=user.id,
        name=_player_name(user)
    )

    await message.reply_text(
        f"✅ تم دخول *{_player_name(user)}* للقيم.",
        parse_mode="Markdown"
    )

    await _update_board(
        context,
        state
    )


# =========================================================
# خروج لاعب
# =========================================================

async def leave_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    player = state.players.get(user.id)

    if not player:
        await message.reply_text(
            "❌ أنت لست داخل القيم."
        )
        return

    del state.players[user.id]

    state.eliminated_players.add(user.id)

    await message.reply_text(
        f"🚪 خرج *{player.name}* من القيم.",
        parse_mode="Markdown"
    )

    # إذا خرج أثناء الجولة الحالية
    if state.started and not state.waiting_continue:
        await _update_board(
            context,
            state
        )

        if len(state.players) < MIN_PLAYERS:
            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    "⚠️ عدد اللاعبين أصبح أقل من "
                    f"{MIN_PLAYERS}.\n"
                    "يمكن للقيم الاستمرار، لكن يجب إضافة لاعب "
                    "بـ`.اضافة` قبل بدء الجولة التالية."
                )
            )

    else:
        await _update_board(
            context,
            state
        )


# =========================================================
# إضافة لاعب بواسطة الأدمن
# =========================================================

async def add_image_quiz_player(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    if not _is_admin(user.id):
        await message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    if not message.reply_to_message:
        await message.reply_text(
            "❌ رد على رسالة الشخص الذي تريد إضافته واكتب:\n"
            "`.اضافة`"
        )
        return

    target = message.reply_to_message.from_user

    if not target:
        await message.reply_text(
            "❌ لم أستطع معرفة الشخص."
        )
        return

    if target.is_bot:
        await message.reply_text(
            "❌ لا يمكنك إضافة بوت."
        )
        return

    if target.id in state.players:
        await message.reply_text(
            "⚠️ الشخص داخل القيم بالفعل."
        )
        return

    # إذا كان خرج سابقًا يسمح له بالدخول مرة أخرى
    state.eliminated_players.discard(
        target.id
    )

    state.players[target.id] = ImagePlayer(
        user_id=target.id,
        name=_player_name(target)
    )

    await message.reply_text(
        f"✅ تمت إضافة *{_player_name(target)}* إلى القيم.",
        parse_mode="Markdown"
    )

    await _update_board(
        context,
        state
    )


# =========================================================
# إعدادات اللعبة
# =========================================================

async def image_quiz_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    if not _is_admin(user.id):
        await message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    if state.started:
        await message.reply_text(
            "❌ لا يمكن تغيير الإعدادات بعد بدء القيم."
        )
        return

    keyboard = []

    row = []

    for points in range(
        MIN_TARGET_POINTS,
        MAX_TARGET_POINTS + 1
    ):
        row.append(
            InlineKeyboardButton(
                f"{points} 🎯",
                callback_data=f"iq:points:{points}"
            )
        )

        if len(row) == 4:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    await message.reply_text(
        (
            "⚙️ *إعدادات توقع الصورة*\n\n"
            "🎯 اختر عدد النقاط المطلوبة للفوز:"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# بدء القيم
# =========================================================

async def begin_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    # أي أدمن يستطيع البدء
    if not _is_admin(user.id):
        await message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    if state.started:
        await message.reply_text(
            "⚠️ القيم بدأ بالفعل."
        )
        return

    if state.target_points is None:
        await message.reply_text(
            "❌ حدد نقاط الفوز أولًا باستخدام `.اعدادات`."
        )
        return

    if len(state.players) < MIN_PLAYERS:
        await message.reply_text(
            f"❌ يجب دخول {MIN_PLAYERS} لاعبين على الأقل."
        )
        return

    state.started = True
    state.finished = False

    await message.reply_text(
        (
            "🚀 *تم بدء القيم!*\n\n"
            f"🎯 الهدف: *{state.target_points} نقاط*\n"
            f"👥 اللاعبين: *{len(state.players)}*"
        ),
        parse_mode="Markdown"
    )

    await start_round(
        context,
        state
    )


# =========================================================
# الجولة التالية
# =========================================================

async def continue_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    if not _is_admin(user.id):
        await message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    if not state.started:
        await message.reply_text(
            "❌ القيم لم يبدأ بعد."
        )
        return

    if state.finished:
        return

    if not state.waiting_continue:
        await message.reply_text(
            "⚠️ الجولة الحالية لم تنتهِ بعد."
        )
        return

    if len(state.players) < MIN_PLAYERS:
        await message.reply_text(
            (
                f"❌ لا يمكن بدء الجولة التالية.\n"
                f"يجب أن يكون هناك {MIN_PLAYERS} لاعبين على الأقل.\n\n"
                "يمكن للأدمن إضافة لاعب باستخدام `.اضافة`."
            )
        )
        return

    await start_round(
        context,
        state
    )


# =========================================================
# إنهاء اللعبة
# =========================================================

async def end_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await _ensure_group(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        return

    if not _is_admin(user.id):
        await message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    await finish_image_quiz(
        context,
        state,
        winner_id=None,
        manual=True
    )


# =========================================================
# إنهاء اللعبة وإعلان النتائج
# =========================================================

async def finish_image_quiz(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
    winner_id: Optional[int] = None,
    manual: bool = False
):
    if state.finished:
        return

    state.finished = True
    state.answer_locked = True
    state.final_guess_phase = False
    state.waiting_continue = False

    # إلغاء المؤقت
    if state.round_task:
        try:
            state.round_task.cancel()
        except Exception:
            pass

    players = list(state.players.values())

    players.sort(
        key=lambda p: (
            p.game_points,
            p.original_points
        ),
        reverse=True
    )

    # إعطاء نقاط البوت الأصلية عند نهاية القيم
    # وليس أثناء كل جولة
    for player in players:
        if player.original_points > 0:
            await _give_original_points(
                player.user_id,
                player.original_points
            )

    lines = [
        "🏁 *انتهت لعبة توقع الصورة!*",
        ""
    ]

    if manual:
        lines.append(
            "🛑 تم إنهاء القيم بواسطة الأدمن."
        )
        lines.append("")

    if winner_id:
        winner = state.players.get(winner_id)

        if winner:
            lines.extend([
                "🏆 *الفائز*",
                f"👑 {winner.name}",
                f"🎯 نقاط القيم: *{winner.game_points}*",
                ""
            ])

    if players:
        lines.append("📊 *النتائج النهائية:*")
        lines.append("")

        for index, player in enumerate(
            players,
            start=1
        ):
            lines.append(
                f"{index}. {player.name}\n"
                f"   🎯 نقاط القيم: {player.game_points}\n"
                f"   💰 النقاط الأصلية: {player.original_points}"
            )
            lines.append("")

    await context.bot.send_message(
        chat_id=state.chat_id,
        text="\n".join(lines),
        parse_mode="Markdown"
    )

    # حذف اللعبة من الألعاب النشطة
    IMAGE_QUIZZES.pop(
        state.chat_id,
        None
    )


# =========================================================
# Callback Buttons
# =========================================================

async def image_quiz_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    message = query.message

    if not message:
        await query.answer()
        return

    chat = message.chat

    if not chat:
        await query.answer()
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        await query.answer(
            "❌ لا توجد لعبة نشطة.",
            show_alert=True
        )
        return

    user = query.from_user

    if not _is_admin(user.id):
        await query.answer(
            "❌ هذا الزر للأدمن فقط.",
            show_alert=True
        )
        return

    data = query.data or ""

    # -----------------------------------------------------
    # فتح إعدادات النقاط
    # -----------------------------------------------------

    if data == "iq:settings":

        if state.started:
            await query.answer(
                "❌ لا يمكن تغيير الإعدادات بعد بدء القيم.",
                show_alert=True
            )
            return

        keyboard = []

        row = []

        for points in range(
            MIN_TARGET_POINTS,
            MAX_TARGET_POINTS + 1
        ):
            row.append(
                InlineKeyboardButton(
                    f"{points} 🎯",
                    callback_data=f"iq:points:{points}"
                )
            )

            if len(row) == 4:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        await query.answer()

        try:
            await query.edit_message_text(
                (
                    "⚙️ *إعدادات توقع الصورة*\n\n"
                    "🎯 اختر عدد النقاط المطلوبة للفوز:"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    keyboard
                )
            )
        except Exception:
            pass

        return

    # -----------------------------------------------------
    # اختيار النقاط
    # -----------------------------------------------------

    if data.startswith("iq:points:"):

        if state.started:
            await query.answer(
                "❌ القيم بدأ بالفعل.",
                show_alert=True
            )
            return

        try:
            points = int(
                data.split(":")[-1]
            )
        except ValueError:
            await query.answer(
                "❌ قيمة غير صحيحة.",
                show_alert=True
            )
            return

        if not (
            MIN_TARGET_POINTS
            <= points
            <= MAX_TARGET_POINTS
        ):
            await query.answer(
                "❌ عدد النقاط غير مسموح.",
                show_alert=True
            )
            return

        state.target_points = points

        await query.answer(
            f"تم تحديد الهدف: {points} نقاط."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "⚙️ تعديل النقاط",
                    callback_data="iq:settings"
                )
            ]
        ]

        try:
            await query.edit_message_text(
                (
                    "🖼️ *توقع الصورة*\n\n"
                    f"🎯 هدف الفوز: *{points} نقاط*\n\n"
                    f"👥 اللاعبين الحاليين: "
                    f"*{len(state.players)}*\n\n"
                    "اكتب `دخول` للانضمام.\n"
                    "وبعد اكتمال اللاعبين يكتب الأدمن `.ابدا`."
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    keyboard
                )
            )
        except Exception:
            pass

        await _update_board(
            context,
            state
        )

        return

    await query.answer()
