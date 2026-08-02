import sqlite3

DB_NAME = "bot.db"

def connect():
    return sqlite3.connect("database.db")


    

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
            'القوت نواف 🎖️'
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

        type TEXT,

        reason TEXT,

        by_user INTEGER,

        date TEXT
    )
    """)



    # =====================
    # الكتم
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mutes
    (
        user_id INTEGER PRIMARY KEY,

        type TEXT,

        reason TEXT,

        by_user INTEGER,

        date TEXT
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
    # المحظورون
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bans
    (
        user_id INTEGER PRIMARY KEY,
        ban_type TEXT,
        reason TEXT,
        admin_id INTEGER
    )
    """)


    # =====================
    # المكتومون
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mutes
    (
        user_id INTEGER PRIMARY KEY,
        mute_type TEXT,
        reason TEXT,
        admin_id INTEGER
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

    try:
        cur.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    except:
        pass

    try:
        cur.execute("ALTER TABLE users ADD COLUMN ban_type TEXT DEFAULT ''")
    except:
        pass

    try:
        cur.execute("ALTER TABLE users ADD COLUMN is_muted INTEGER DEFAULT 0")
    except:
        pass

    try:
        cur.execute("ALTER TABLE users ADD COLUMN mute_type TEXT DEFAULT ''")
    except:
        pass


    # =====================
    # الحظر
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bans
    (
        user_id INTEGER PRIMARY KEY,
        ban_type TEXT DEFAULT 'normal'
    )
    """)


    # =====================
    # الكتم
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mutes
    (
        user_id INTEGER PRIMARY KEY,
        mute_type TEXT DEFAULT 'normal'
    )
    """)

    # =====================
    # الحظر
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bans
    (
        user_id INTEGER PRIMARY KEY,
        ban_type TEXT,
        until_time TEXT,
        reason TEXT
    )
    """)
    try:
        cur.execute(
            "ALTER TABLE bans ADD COLUMN until_time TEXT"
        )
    except:
        pass


    try:
        cur.execute(
            "ALTER TABLE bans ADD COLUMN reason TEXT"
        )
    except:
        pass


    # =====================
    # الكتم
    # =====================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mutes
    (
        user_id INTEGER PRIMARY KEY,
        mute_type TEXT,
        until_time TEXT,
        reason TEXT
    )
    """)
    try:
        cur.execute(
            "ALTER TABLE mutes ADD COLUMN reason TEXT"
        )
    except:
        pass

        try:
        cur.execute(
            "ALTER TABLE mutes ADD COLUMN until_time TEXT"
        )
    except:
        pass


    try:
        cur.execute(
            "ALTER TABLE mutes ADD COLUMN reason TEXT"
        )
    except:
        pass


    conn.commit()
    conn.close()