import io
import json
import os
import time

import requests
from PIL import Image


# =========================================================
# الإعدادات
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGES_DIR = os.path.join(
    BASE_DIR,
    "images",
    "animals",
)

QUESTIONS_FILE = os.path.join(
    BASE_DIR,
    "questions.json",
)

SOURCES_FILE = os.path.join(
    BASE_DIR,
    "animals_sources.json",
)

OPENVERSE_URL = "https://api.openverse.org/v1/images/"

TARGET_COUNT = 80

MIN_WIDTH = 500
MIN_HEIGHT = 500

# أسماء الحيوانات
ANIMALS = [
    ("أسد", "lion"),
    ("نمر", "tiger"),
    ("فهد", "cheetah"),
    ("ذئب", "wolf"),
    ("ثعلب", "fox"),
    ("دب", "bear"),
    ("فيل", "elephant"),
    ("زرافة", "giraffe"),
    ("حمار وحشي", "zebra"),
    ("وحيد القرن", "rhinoceros"),
    ("فرس النهر", "hippopotamus"),
    ("غوريلا", "gorilla"),
    ("شمبانزي", "chimpanzee"),
    ("أورانغوتان", "orangutan"),
    ("باندا", "giant panda"),
    ("كوالا", "koala"),
    ("كنغر", "kangaroo"),
    ("كسلان", "sloth"),
    ("غزال", "gazelle"),
    ("حمار", "donkey"),
    ("حصان", "horse"),
    ("جمل", "camel"),
    ("بقرة", "cow"),
    ("خروف", "sheep"),
    ("ماعز", "goat"),
    ("خنزير", "pig"),
    ("أرنب", "rabbit"),
    ("قنفذ", "hedgehog"),
    ("سنجاب", "squirrel"),
    ("فأر", "mouse"),
    ("قط", "cat"),
    ("كلب", "dog"),
    ("بومة", "owl"),
    ("نسر", "eagle"),
    ("صقر", "falcon"),
    ("ببغاء", "parrot"),
    ("طاووس", "peacock"),
    ("فلامنغو", "flamingo"),
    ("بطريق", "penguin"),
    ("بطة", "duck"),
    ("دجاجة", "chicken"),
    ("ديك", "rooster"),
    ("نعامة", "ostrich"),
    ("بجعة", "swan"),
    ("نقار الخشب", "woodpecker"),
    ("حمامة", "pigeon"),
    ("غراب", "crow"),
    ("كناري", "canary"),
    ("بومة ثلجية", "snowy owl"),
    ("سلحفاة", "turtle"),
    ("تمساح", "crocodile"),
    ("أفعى", "snake"),
    ("كوبرا", "cobra"),
    ("حرباء", "chameleon"),
    ("ضفدع", "frog"),
    ("سمندر", "salamander"),
    ("قرش", "shark"),
    ("دولفين", "dolphin"),
    ("حوت", "whale"),
    ("أخطبوط", "octopus"),
    ("حبار", "squid"),
    ("قنديل البحر", "jellyfish"),
    ("فرس البحر", "seahorse"),
    ("نجم البحر", "starfish"),
    ("سرطان البحر", "crab"),
    ("روبيان", "shrimp"),
    ("سلطعون", "crayfish"),
    ("فراشة", "butterfly"),
    ("نحلة", "bee"),
    ("نملة", "ant"),
    ("دعسوقة", "ladybug"),
    ("جرادة", "grasshopper"),
    ("يعسوب", "dragonfly"),
    ("عنكبوت", "spider"),
    ("عقرب", "scorpion"),
    ("حلزون", "snail"),
    ("خفاش", "bat"),
    ("قندس", "beaver"),
    ("راكون", "raccoon"),
    ("قضاعة", "otter"),
]


# =========================================================
# إنشاء المجلدات
# =========================================================

os.makedirs(IMAGES_DIR, exist_ok=True)


# =========================================================
# أدوات
# =========================================================

def download_image(url):
    """
    تحميل الصورة من الرابط وإرجاع البيانات.
    """

    try:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 ImageQuizDownloader/1.0"
            },
        )

        response.raise_for_status()

        return response.content

    except Exception as e:
        print(f"   ❌ فشل التحميل: {e}")
        return None


def convert_to_jpg(data, output_path):
    """
    تحويل الصورة إلى JPG مع التأكد من الحجم.
    """

    try:
        image = Image.open(io.BytesIO(data))

        image.load()

        width, height = image.size

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            print(
                f"   ⚠️ الصورة صغيرة جدًا: "
                f"{width}x{height}"
            )
            return False

        # تحويل الصور ذات الشفافية إلى RGB
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new(
                "RGB",
                image.size,
                "white",
            )

            if image.mode == "P":
                image = image.convert("RGBA")

            background.paste(
                image,
                mask=image.getchannel("A")
                if image.mode == "RGBA"
                else None,
            )

            image = background

        else:
            image = image.convert("RGB")

        # تصغير الصور الكبيرة جدًا
        image.thumbnail(
            (1600, 1600),
            Image.Resampling.LANCZOS,
        )

        image.save(
            output_path,
            "JPEG",
            quality=88,
            optimize=True,
        )

        return True

    except Exception as e:
        print(f"   ❌ الصورة غير صالحة: {e}")
        return False


def search_openverse(search_term):
    """
    البحث عن صورة مناسبة في Openverse.
    """

    params = {
        "q": search_term,
        "license": "cc0,pdm,by",
        "page_size": 20,
        "mature": "false",
    }

    try:
        response = requests.get(
            OPENVERSE_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 ImageQuizDownloader/1.0"
            },
        )

        response.raise_for_status()

        data = response.json()

        return data.get("results", [])

    except Exception as e:
        print(f"   ❌ فشل البحث: {e}")
        return []


# =========================================================
# تحميل الحيوانات
# =========================================================

def main():

    print("=" * 60)
    print("🐾 تحميل صور الحيوانات")
    print("=" * 60)

    print()
    print(f"📁 المجلد:")
    print(IMAGES_DIR)

    print()
    print(f"🐾 عدد الحيوانات: {len(ANIMALS)}")
    print()

    questions = []
    sources = []

    success_count = 0

    for index, (arabic_name, search_term) in enumerate(
        ANIMALS,
        start=1,
    ):

        filename = f"{index:03d}.jpg"

        output_path = os.path.join(
            IMAGES_DIR,
            filename,
        )

        print(
            f"[{index:02d}/{len(ANIMALS)}] "
            f"{arabic_name}"
        )

        # إذا الصورة موجودة مسبقًا
        if os.path.exists(output_path):

            print("   ✅ الصورة موجودة مسبقًا")

            success_count += 1

            questions.append(
                {
                    "id": index,
                    "image": f"images/animals/{filename}",
                    "answer": arabic_name,
                    "alternative_answers": [],
                    "category": "animals",
                    "difficulty": "easy",
                }
            )

            sources.append(
                {
                    "id": index,
                    "answer": arabic_name,
                    "image": f"images/animals/{filename}",
                    "status": "already_exists",
                }
            )

            continue

        results = search_openverse(search_term)

        if not results:
            print("   ❌ لم يتم العثور على صور")
            print()

            continue

        downloaded = False

        for result in results:

            image_url = (
                result.get("url")
                or result.get("thumbnail")
            )

            if not image_url:
                continue

            license_code = (
                result.get("license")
                or ""
            ).lower()

            if license_code not in {
                "cc0",
                "pdm",
                "by",
            }:
                continue

            print("   ⬇️ تحميل الصورة...")

            image_data = download_image(
                image_url
            )

            if not image_data:
                continue

            if not convert_to_jpg(
                image_data,
                output_path,
            ):
                continue

            print(
                f"   ✅ تم الحفظ: {filename}"
            )

            questions.append(
                {
                    "id": index,
                    "image": f"images/animals/{filename}",
                    "answer": arabic_name,
                    "alternative_answers": [],
                    "category": "animals",
                    "difficulty": "easy",
                }
            )

            sources.append(
                {
                    "id": index,
                    "answer": arabic_name,
                    "image": f"images/animals/{filename}",
                    "source": result.get(
                        "foreign_landing_url"
                    ),
                    "creator": result.get(
                        "creator"
                    ),
                    "creator_url": result.get(
                        "creator_url"
                    ),
                    "license": result.get(
                        "license"
                    ),
                    "license_version": result.get(
                        "license_version"
                    ),
                    "license_url": result.get(
                        "license_url"
                    ),
                    "original_url": image_url,
                }
            )

            success_count += 1
            downloaded = True

            break

        if not downloaded:
            print(
                "   ❌ لم أستطع الحصول على صورة مناسبة"
            )

        print()

        # حتى لا نرسل طلبات كثيرة بسرعة
        time.sleep(0.5)

    # =====================================================
    # تحديث questions.json
    # =====================================================

    existing_questions = []

    if os.path.exists(QUESTIONS_FILE):

        try:

            with open(
                QUESTIONS_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                existing_questions = json.load(file)

                if not isinstance(
                    existing_questions,
                    list,
                ):
                    existing_questions = []

        except Exception:
            existing_questions = []

    # حذف أسئلة الحيوانات القديمة
    existing_questions = [
        question
        for question in existing_questions
        if question.get("category") != "animals"
    ]

    # إضافة الأسئلة الجديدة
    existing_questions.extend(questions)

    # ترتيب حسب ID
    existing_questions.sort(
        key=lambda item: str(item.get("id", ""))
    )

    with open(
        QUESTIONS_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            existing_questions,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # =====================================================
    # حفظ المصادر
    # =====================================================

    with open(
        SOURCES_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            sources,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # =====================================================
    # النتيجة
    # =====================================================

    print("=" * 60)

    print(
        f"✅ تم تحميل {success_count} "
        f"من أصل {TARGET_COUNT} صورة."
    )

    print()

    print(
        f"📁 الصور:"
    )

    print(
        "games/image_quiz/images/animals/"
    )

    print()

    print(
        "📄 تم تحديث:"
    )

    print(
        "games/image_quiz/questions.json"
    )

    print()

    print(
        "📄 تم إنشاء:"
    )

    print(
        "games/image_quiz/animals_sources.json"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()