import json
import os
import time
import random
import requests

from PIL import Image
from io import BytesIO


# =========================================================
# الإعدادات
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QUESTIONS_FILE = os.path.join(
    BASE_DIR,
    "questions.json",
)

IMAGES_DIR = os.path.join(
    BASE_DIR,
    "images",
)

SOURCES_DIR = os.path.join(
    BASE_DIR,
    "sources",
)

OPENVERSE_API = (
    "https://api.openverse.org/v1/images/"
)

MIN_WIDTH = 500
MIN_HEIGHT = 500

SEARCH_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 30

# عدد محاولات API عند 429
MAX_RETRIES = 5

# وقت الانتظار الأساسي عند 429
BACKOFF_BASE = 10

# تأخير طبيعي بين طلبات البحث
SEARCH_DELAY = 2.5

# تأخير بسيط بين تحميل الصور
IMAGE_DELAY = 0.8

# عدد نتائج البحث
PAGE_SIZE = 20


# =========================================================
# الفئات
# =========================================================

CATEGORIES = {
    "vehicles": {
        "count": 60,
        "searches": [
            "car",
            "sports car",
            "bus",
            "truck",
            "motorcycle",
            "bicycle",
            "train",
            "airplane",
            "helicopter",
            "ship",
            "boat",
            "taxi",
        ],
    },

    "food": {
        "count": 60,
        "searches": [
            "pizza",
            "burger",
            "fries",
            "sandwich",
            "pasta",
            "rice",
            "cake",
            "donut",
            "ice cream",
            "chocolate",
            "apple",
            "banana",
            "orange",
            "watermelon",
            "strawberry",
            "coffee",
            "tea",
            "juice",
            "milk",
            "bread",
        ],
    },

    "football": {
        "count": 60,
        "searches": [
            "football player",
            "soccer player",
            "football match",
            "footballer",
            "soccer",
            "football stadium",
        ],
    },

    "gaming": {
        "count": 50,
        "searches": [
            "gaming controller",
            "game controller",
            "video game console",
            "PlayStation controller",
            "Xbox controller",
            "Nintendo controller",
            "gaming keyboard",
            "gaming mouse",
            "gaming headset",
            "computer gaming",
        ],
    },

    "household": {
        "count": 60,
        "searches": [
            "chair",
            "table",
            "sofa",
            "bed",
            "lamp",
            "television",
            "refrigerator",
            "washing machine",
            "microwave",
            "kitchen",
            "cup",
            "plate",
            "spoon",
            "fork",
            "door",
            "window",
            "clock",
            "mirror",
            "vacuum cleaner",
            "toilet",
        ],
    },

    "technology": {
        "count": 30,
        "searches": [
            "smartphone",
            "mobile phone",
            "computer",
            "laptop",
            "tablet",
            "camera",
            "smartwatch",
            "keyboard",
            "mouse",
            "headphones",
            "computer monitor",
        ],
    },

    "everyday": {
        "count": 20,
        "searches": [
            "backpack",
            "umbrella",
            "shoes",
            "wallet",
            "keys",
            "bottle",
            "glasses",
            "book",
            "pen",
            "pencil",
            "scissors",
            "ball",
        ],
    },

    "anime": {
        "count": 80,
        "searches": [
            "anime character",
            "anime drawing",
            "anime illustration",
            "Japanese animation character",
            "manga character",
        ],
    },
}


TOTAL = sum(
    item["count"]
    for item in CATEGORIES.values()
)


# =========================================================
# Session
# =========================================================

SESSION = requests.Session()

SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; ImageQuizDownloader/1.0)"
        ),
        "Accept": "application/json",
    }
)


# =========================================================
# قراءة الأسئلة
# =========================================================

def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        return []

    try:
        with open(
            QUESTIONS_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return data

    except Exception as e:
        print(
            f"❌ خطأ في قراءة questions.json: {e}"
        )
        return []


# =========================================================
# حفظ الأسئلة
# =========================================================

def save_questions(questions):
    temp_file = QUESTIONS_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            questions,
            f,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        temp_file,
        QUESTIONS_FILE,
    )


# =========================================================
# حفظ المصادر
# =========================================================

def save_source(
    category,
    filename,
    result,
):
    os.makedirs(
        SOURCES_DIR,
        exist_ok=True,
    )

    source_file = os.path.join(
        SOURCES_DIR,
        f"{category}.json",
    )

    data = []

    if os.path.exists(source_file):
        try:
            with open(
                source_file,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            if not isinstance(data, list):
                data = []

        except Exception:
            data = []

    data.append(
        {
            "file": filename,
            "title": result.get(
                "title",
                "",
            ),
            "creator": result.get(
                "creator",
                "",
            ),
            "license": result.get(
                "license",
                "",
            ),
            "license_version": result.get(
                "license_version",
                "",
            ),
            "source": result.get(
                "source",
                "",
            ),
            "provider": result.get(
                "provider",
                "",
            ),
            "url": result.get(
                "url",
                "",
            ),
            "foreign_landing_url": result.get(
                "foreign_landing_url",
                "",
            ),
        }
    )

    with open(
        source_file,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# تنظيف النص
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return (
        str(text)
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


# =========================================================
# البحث في Openverse
# =========================================================

def search_openverse(
    query,
    page=1,
    page_size=PAGE_SIZE,
):
    params = {
        "q": query,
        "page": page,
        "page_size": page_size,

        # نحصر النتائج في التراخيص المفتوحة.
        "license": "cc0,pdm,by",
    }

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:
            response = SESSION.get(
                OPENVERSE_API,
                params=params,
                timeout=SEARCH_TIMEOUT,
            )

        except requests.RequestException as e:
            print(
                f"⚠️ خطأ اتصال Openverse: {e}"
            )

            wait_time = (
                BACKOFF_BASE * attempt
            )

            print(
                f"⏳ انتظار {wait_time} ثانية..."
            )

            time.sleep(wait_time)

            continue

        status = response.status_code

        # -------------------------------------------------
        # نجاح
        # -------------------------------------------------

        if status == 200:
            try:
                data = response.json()

            except ValueError:
                print(
                    "⚠️ Openverse أرسل استجابة "
                    "غير صالحة."
                )
                return []

            return data.get(
                "results",
                [],
            )

        # -------------------------------------------------
        # Rate Limit
        # -------------------------------------------------

        if status == 429:

            retry_after = response.headers.get(
                "Retry-After"
            )

            if retry_after:
                try:
                    wait_time = int(
                        retry_after
                    )
                except ValueError:
                    wait_time = (
                        BACKOFF_BASE * attempt
                    )
            else:
                wait_time = (
                    BACKOFF_BASE
                    * attempt
                )

            # هامش عشوائي صغير
            wait_time += random.randint(
                1,
                4,
            )

            print(
                f"⚠️ Openverse HTTP 429 "
                f"للبحث: {query}"
            )

            print(
                f"⏳ Rate Limit — "
                f"الانتظار {wait_time} ثانية..."
            )

            time.sleep(wait_time)

            continue

        # -------------------------------------------------
        # Unauthorized
        # -------------------------------------------------

        if status == 401:

            print(
                f"❌ Openverse HTTP 401 "
                f"للبحث: {query}"
            )

            print(
                "⚠️ تم رفض طلب API."
            )

            print(
                "⏳ لن نكرر الطلب بسرعة."
            )

            time.sleep(
                15
            )

            return []

        # -------------------------------------------------
        # أخطاء أخرى
        # -------------------------------------------------

        print(
            f"⚠️ Openverse HTTP {status} "
            f"للبحث: {query}"
        )

        return []

    print(
        f"❌ فشلت محاولات البحث: {query}"
    )

    return []


# =========================================================
# تحميل الصورة
# =========================================================

def download_image(url):

    if not url:
        return None

    try:
        response = SESSION.get(
            url,
            timeout=DOWNLOAD_TIMEOUT,
        )

        if response.status_code != 200:
            return None

        if not response.content:
            return None

        image = Image.open(
            BytesIO(response.content)
        )

        image.load()

        width, height = image.size

        if (
            width < MIN_WIDTH
            or height < MIN_HEIGHT
        ):
            return None

        # -------------------------------------------------
        # RGB / RGBA
        # -------------------------------------------------

        if image.mode == "RGBA":

            background = Image.new(
                "RGB",
                image.size,
                "white",
            )

            background.paste(
                image,
                mask=image.getchannel("A"),
            )

            image = background

        else:
            image = image.convert(
                "RGB"
            )

        return image

    except Exception:
        return None


# =========================================================
# حفظ الصورة
# =========================================================

def save_image(
    image,
    path,
):
    try:

        os.makedirs(
            os.path.dirname(path),
            exist_ok=True,
        )

        image.save(
            path,
            "JPEG",
            quality=92,
            optimize=True,
        )

        return True

    except Exception as e:

        print(
            f"❌ فشل حفظ الصورة: {e}"
        )

        return False


# =========================================================
# هل السؤال موجود؟
# =========================================================

def question_exists(
    questions,
    image_path,
):
    normalized = image_path.replace(
        "\\",
        "/",
    )

    for question in questions:

        existing = str(
            question.get(
                "image",
                "",
            )
        ).replace(
            "\\",
            "/",
        )

        if existing == normalized:
            return True

    return False


# =========================================================
# الرقم التالي
# =========================================================

def next_category_number(
    questions,
    category,
):
    numbers = []

    prefix = f"{category}_"

    for question in questions:

        question_id = str(
            question.get(
                "id",
                "",
            )
        )

        if not question_id.startswith(
            prefix
        ):
            continue

        try:

            number = int(
                question_id[
                    len(prefix):
                ]
            )

            numbers.append(
                number
            )

        except ValueError:
            continue

    if not numbers:
        return 1

    return max(numbers) + 1


# =========================================================
# اسم الإجابة
# =========================================================

def make_answer(
    category,
    query,
    title,
):
    title = clean_text(
        title
    )

    if title:
        return title

    return clean_text(
        query
    )


# =========================================================
# عدد الصور الموجودة فعليًا
# =========================================================

def get_existing_images(
    category_dir,
):
    if not os.path.exists(
        category_dir
    ):
        return []

    files = []

    for name in os.listdir(
        category_dir
    ):

        if name.lower().endswith(
            (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
            )
        ):
            files.append(name)

    return files


# =========================================================
# تنزيل فئة
# =========================================================

def download_category(
    category,
    settings,
    questions,
):

    target = settings["count"]

    searches = settings[
        "searches"
    ]

    category_dir = os.path.join(
        IMAGES_DIR,
        category,
    )

    os.makedirs(
        category_dir,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # الموجود
    # -----------------------------------------------------

    existing_files = (
        get_existing_images(
            category_dir
        )
    )

    current_count = len(
        existing_files
    )

    print()
    print("=" * 60)
    print(
        f"📂 الفئة: {category}"
    )
    print(
        f"🎯 المطلوب: {target}"
    )
    print(
        f"📦 الموجود: {current_count}"
    )
    print("=" * 60)

    if current_count >= target:

        print(
            "✅ الفئة مكتملة."
        )

        return

    next_number = (
        next_category_number(
            questions,
            category,
        )
    )

    # -----------------------------------------------------
    # منع استخدام نفس الرابط
    # -----------------------------------------------------

    used_urls = set()

    for question in questions:

        url = question.get(
            "source_url"
        )

        if url:
            used_urls.add(
                url
            )

    search_index = 0

    page = 1

    empty_searches = 0

    # -----------------------------------------------------
    # الحلقة
    # -----------------------------------------------------

    while current_count < target:

        query = searches[
            search_index
            % len(searches)
        ]

        print()
        print(
            f"🔎 بحث: {query} "
            f"(صفحة {page})"
        )

        results = search_openverse(
            query=query,
            page=page,
            page_size=PAGE_SIZE,
        )

        # -------------------------------------------------
        # لا توجد نتائج
        # -------------------------------------------------

        if not results:

            empty_searches += 1

            search_index += 1

            page = 1

            # إذا فشلت كل عمليات البحث
            # نتوقف بدل الدوران بلا نهاية.

            if (
                empty_searches
                >= len(searches) * 2
            ):

                print(
                    "⚠️ لم نجد نتائج "
                    "إضافية مناسبة."
                )

                break

            # لا نضرب API مباشرة
            time.sleep(
                SEARCH_DELAY
            )

            continue

        empty_searches = 0

        # -------------------------------------------------
        # معالجة النتائج
        # -------------------------------------------------

        downloaded_this_page = 0

        for result in results:

            if current_count >= target:
                break

            url = (
                result.get("url")
                or result.get(
                    "thumbnail"
                )
            )

            if not url:
                continue

            if url in used_urls:
                continue

            used_urls.add(
                url
            )

            print(
                "   ⬇️ محاولة تحميل صورة..."
            )

            image = download_image(
                url
            )

            if image is None:
                continue

            filename = (
                f"{next_number:03d}.jpg"
            )

            file_path = os.path.join(
                category_dir,
                filename,
            )

            if os.path.exists(
                file_path
            ):

                next_number += 1

                continue

            if not save_image(
                image,
                file_path,
            ):
                continue

            relative_path = (
                f"images/{category}/"
                f"{filename}"
            )

            title = clean_text(
                result.get(
                    "title",
                    "",
                )
            )

            answer = make_answer(
                category,
                query,
                title,
            )

            question_id = (
                f"{category}_"
                f"{next_number:03d}"
            )

            # -------------------------------------------------
            # السؤال
            # -------------------------------------------------

            question = {
                "id": question_id,

                "image": relative_path,

                "answer": answer,

                "alternative_answers": [],

                "category": category,

                "difficulty": "medium",

                "source_url": url,

                "license": result.get(
                    "license",
                    "",
                ),

                "license_version": result.get(
                    "license_version",
                    "",
                ),
            }

            # -------------------------------------------------
            # أضف السؤال
            # -------------------------------------------------

            if not question_exists(
                questions,
                relative_path,
            ):

                questions.append(
                    question
                )

            # -------------------------------------------------
            # احفظ المصدر
            # -------------------------------------------------

            save_source(
                category,
                filename,
                result,
            )

            # -------------------------------------------------
            # تحديث
            # -------------------------------------------------

            current_count += 1

            next_number += 1

            downloaded_this_page += 1

            print(
                f"✅ {current_count}/"
                f"{target} "
                f"{relative_path}"
            )

            # حفظ مباشر
            save_questions(
                questions
            )

            # لا تضغط على المصدر
            time.sleep(
                IMAGE_DELAY
            )

        # -------------------------------------------------
        # الانتقال للصفحة التالية
        # -------------------------------------------------

        page += 1

        if page > 10:

            page = 1

            search_index += 1

        # -------------------------------------------------
        # إذا لم نجد أي صورة في الصفحة
        # -------------------------------------------------

        if downloaded_this_page == 0:

            time.sleep(
                SEARCH_DELAY
            )

        else:

            time.sleep(
                SEARCH_DELAY
            )

        # -------------------------------------------------
        # تدوير عمليات البحث
        # -------------------------------------------------

        if search_index >= len(
            searches
        ):

            search_index = 0

    print()

    print(
        f"🏁 انتهت {category}: "
        f"{current_count}/{target}"
    )


# =========================================================
# التحقق
# =========================================================

def verify_questions(
    questions,
):

    print()
    print("=" * 60)
    print("🔍 فحص الصور")
    print("=" * 60)

    missing = []

    for question in questions:

        image_path = question.get(
            "image",
            "",
        )

        if not image_path:
            continue

        full_path = os.path.join(
            BASE_DIR,
            image_path,
        )

        if not os.path.exists(
            full_path
        ):

            missing.append(
                (
                    question.get(
                        "id"
                    ),
                    image_path,
                )
            )

    if not missing:

        print(
            "✅ كل الأسئلة لها صور."
        )

        return

    print(
        f"⚠️ صور مفقودة: "
        f"{len(missing)}"
    )

    for (
        question_id,
        image_path,
    ) in missing[:30]:

        print(
            f"❌ {question_id}: "
            f"{image_path}"
        )


# =========================================================
# إحصائيات
# =========================================================

def print_statistics(
    questions,
):

    print()
    print("=" * 60)
    print("📊 إحصائيات المكتبة")
    print("=" * 60)

    for category, settings in (
        CATEGORIES.items()
    ):

        category_dir = os.path.join(
            IMAGES_DIR,
            category,
        )

        count = len(
            get_existing_images(
                category_dir
            )
        )

        target = settings[
            "count"
        ]

        print(
            f"📂 {category}: "
            f"{count}/{target}"
        )

    total_files = 0

    for root, dirs, files in os.walk(
        IMAGES_DIR
    ):

        for filename in files:

            if filename.lower().endswith(
                (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                )
            ):

                total_files += 1

    print()
    print(
        f"🖼️ إجمالي الصور: "
        f"{total_files}"
    )


# =========================================================
# Main
# =========================================================

def main():

    print()
    print(
        "🎯 Image Quiz Downloader"
    )

    print(
        "📦 تحميل مكتبة توقع الصورة"
    )

    print()

    questions = load_questions()

    print(
        f"📄 الأسئلة الحالية: "
        f"{len(questions)}"
    )

    print(
        f"🖼️ المطلوب من الصور الجديدة: "
        f"{TOTAL}"
    )

    print()

    # -----------------------------------------------------
    # كل الفئات
    # -----------------------------------------------------

    for (
        category,
        settings,
    ) in CATEGORIES.items():

        download_category(
            category,
            settings,
            questions,
        )

    # -----------------------------------------------------
    # حفظ نهائي
    # -----------------------------------------------------

    save_questions(
        questions
    )

    # -----------------------------------------------------
    # النتيجة
    # -----------------------------------------------------

    print()
    print("=" * 60)
    print("🎉 انتهى التحميل")
    print("=" * 60)

    print(
        f"📄 إجمالي الأسئلة: "
        f"{len(questions)}"
    )

    print_statistics(
        questions
    )

    verify_questions(
        questions
    )

    print()

    print(
        "⚠️ تنبيه:"
    )

    print(
        "Openverse يعرض أعمالًا مفتوحة "
        "الترخيص، لكن يجب التحقق من "
        "ترخيص كل صورة قبل استخدامها."
    )


# =========================================================
# تشغيل
# =========================================================

if __name__ == "__main__":
    main()