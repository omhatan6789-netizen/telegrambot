import sqlite3
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "database.db")

 
def connect():
    return sqlite3.connect(DB_NAME)


def create_tables():

    conn = connect()
    cur = conn.cursor()

    # =====================
    # المستخدمين
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users
    (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        messages INTEGER DEFAULT 0,
        rank TEXT DEFAULT 'عضو',
        joined_date TEXT
    )
    """)

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (
            user_id,
            rank
        )
        VALUES
        (
            8453977662,
            'المالك'
        )
        """
    )

    # =====================
    # الردود العادية
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS replies
    (
        name TEXT PRIMARY KEY,
        text TEXT,
        type TEXT,
        caption TEXT
    )
    """)

    # =====================
    # الردود المميزة
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS special_replies
    (
        name TEXT PRIMARY KEY,
        text TEXT,
        type TEXT,
        caption TEXT
    )
    """)

    # =====================
    # النقاط
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS points
    (
        user_id INTEGER PRIMARY KEY,
        points INTEGER DEFAULT 0
    )
    """)

    # =====================
    # الألعاب
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS games
    (
        name TEXT PRIMARY KEY,
        image TEXT,
        status TEXT DEFAULT 'on'
    )
    """)

    # =====================
    # أسئلة الألعاب
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS game_questions
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_name TEXT,
        question TEXT,
        image TEXT,
        caption TEXT,
        answers TEXT
    )
    """)

    # =====================
    # إعدادات الألعاب
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS games_settings
    (
        id INTEGER PRIMARY KEY,
        status TEXT DEFAULT 'on'
    )
    """)

    cur.execute(
        """
        INSERT OR IGNORE INTO games_settings
        (
            id,
            status
        )
        VALUES
        (
            1,
            'on'
        )
        """
    )

    # =====================
    # سجل الفائزين
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS winners
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        game_name TEXT,
        points INTEGER DEFAULT 3,
        date TEXT
    )
    """)

    # =====================
    # سلسلة الانتصارات
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS win_streaks
    (
        user_id INTEGER PRIMARY KEY,
        streak INTEGER DEFAULT 0
    )
    """)

    # =====================
    # الجوائز اليومية
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_rewards
    (
        user_id INTEGER PRIMARY KEY,
        last_reward TEXT
    )
    """)

    # =====================
    # الرتب
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ranks
    (
        user_id INTEGER PRIMARY KEY,
        rank TEXT
    )
    """)

    # =====================
    # المشرفين
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins
    (
        user_id INTEGER PRIMARY KEY,
        rank TEXT
    )
    """)

    # =====================
    # الحظر
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bans
    (
        user_id INTEGER PRIMARY KEY,
        ban_type TEXT DEFAULT 'normal',
        until_time TEXT,
        reason TEXT,
        by_user INTEGER
    )
    """)

    # =====================
    # الكتم
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mutes
    (
        user_id INTEGER PRIMARY KEY,
        mute_type TEXT DEFAULT 'normal',
        until_time TEXT,
        reason TEXT,
        by_user INTEGER
    )
    """)

    # =====================
    # سجل الإدارة
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS moderation_logs
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        user_id INTEGER,
        by_user INTEGER,
        date TEXT
    )
    """)

    # =====================
    # السجل الإداري
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_logs
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        target_id INTEGER,
        action TEXT,
        date TEXT
    )
    """)

    # =====================
    # قفل الأوامر
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS command_locks
    (
        command TEXT PRIMARY KEY,
        rank TEXT NOT NULL
    )
    """)

    # =====================
    # الأوامر المضافة
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS custom_commands
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        old_command TEXT,
        new_command TEXT UNIQUE
    )
    """)

    # ==================================================
    # تحديثات آمنة للجدول القديم users
    # ==================================================

    user_columns = [
        ("is_banned", "INTEGER DEFAULT 0"),
        ("ban_type", "TEXT DEFAULT ''"),
        ("is_muted", "INTEGER DEFAULT 0"),
        ("mute_type", "TEXT DEFAULT ''")
    ]

    for column_name, column_type in user_columns:

        try:
            cur.execute(
                f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
            )
        except sqlite3.OperationalError:
            pass

    # ==================================================
    # نظام المطورين
    # ==================================================
    #
    # primary:
    # المطور الأساسي
    #
    # secondary:
    # مطور مرفوع من المطور الأساسي
    #
    # هذا الجدول منفصل عن users حتى نقدر نعطي
    # المطور المساعد صلاحيات قوية مع بقاء المطور
    # الأساسي أعلى منه.
    #
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS developers
    (
        user_id INTEGER PRIMARY KEY,
        developer_type TEXT NOT NULL DEFAULT 'secondary',
        added_by INTEGER,
        added_date TEXT
    )
    """)

    # ==================================================
    # صلاحيات المطورين
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS developer_permissions
    (
        user_id INTEGER,
        permission TEXT,
        allowed INTEGER DEFAULT 1,

        PRIMARY KEY
        (
            user_id,
            permission
        )
    )
    """)

    # ==================================================
    # منع/سماح صلاحيات الأشخاص
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_permissions
    (
        user_id INTEGER,
        permission TEXT,
        allowed INTEGER DEFAULT 1,

        PRIMARY KEY
        (
            user_id,
            permission
        )
    )
    """)

    # ==================================================
    # إعدادات القروبات
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_settings
    (
        chat_id INTEGER PRIMARY KEY,
        created_date TEXT
    )
    """)

    # ==================================================
    # إعدادات الحماية لكل قروب
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS protection_settings
    (
        chat_id INTEGER PRIMARY KEY,

        repetition_enabled INTEGER DEFAULT 0,
        repetition_limit INTEGER DEFAULT 3,
        repetition_seconds INTEGER DEFAULT 5,
        repetition_action TEXT DEFAULT 'mute',

        links_enabled INTEGER DEFAULT 0,
        mentions_enabled INTEGER DEFAULT 0,
        spam_enabled INTEGER DEFAULT 0
    )
    """)

    # ==================================================
    # الكلمات المحظورة
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blocked_words
    (
        chat_id INTEGER,
        word TEXT,

        PRIMARY KEY
        (
            chat_id,
            word
        )
    )
    """)

    # ==================================================
    # إعدادات الكلمات المحظورة
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blocked_words_settings
    (
        chat_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 0,
        action TEXT DEFAULT 'mute'
    )
    """)

    # ==================================================
    # رسائل البوت القابلة للتعديل
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bot_messages
    (
        message_key TEXT PRIMARY KEY,
        message_text TEXT
    )
    """)

    # ==================================================
    # إعدادات أزرار اللوحات
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS panel_buttons
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        panel TEXT,
        button_key TEXT,
        button_text TEXT,
        button_url TEXT,
        row_number INTEGER DEFAULT 0,
        button_order INTEGER DEFAULT 0
    )
    """)

    # ==================================================
    # بيانات المطور والمالك
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS profile_settings
    (
        profile_type TEXT PRIMARY KEY,

        user_id INTEGER,
        username TEXT
    )
    """)

    # ==================================================
    # المطور الأساسي
    # ==================================================

    cur.execute(
        """
        INSERT OR IGNORE INTO developers
        (
            user_id,
            developer_type
        )
        VALUES
        (
            8453977662,
            'primary'
        )
        """
    )

    # ==================================================
    # حفظ التغييرات
    # ==================================================

    # ==================================================
    # منع/سماح صلاحيات المستخدمين لكل قروب
    # ==================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_user_permissions
    (
        chat_id INTEGER,
        user_id INTEGER,
        permission TEXT,
        allowed INTEGER DEFAULT 0,

        PRIMARY KEY
        (
            chat_id,
            user_id,
            permission
        )
    )
    """)

    conn.commit()
    conn.close()