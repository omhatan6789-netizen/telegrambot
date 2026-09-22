import os
import psycopg2
from psycopg2 import pool

# ==================================================
# Supabase
# ==================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL غير موجود في Environment Variables"
    )

# ==================================================
# Connection Pool
# ==================================================

DB_POOL = None


def get_pool():
    global DB_POOL

    if DB_POOL is None:
        DB_POOL = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
        )

    return DB_POOL


# ==================================================
# Cursor يدعم ? مثل SQLite
# ==================================================

class CompatibleCursor:

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):

        if isinstance(query, str):
            query = query.replace("?", "%s")

        return self._cursor.execute(query, params)

    def executemany(self, query, params_seq):

        if isinstance(query, str):
            query = query.replace("?", "%s")

        return self._cursor.executemany(
            query,
            params_seq
        )

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchmany(self, size=None):

        if size is None:
            return self._cursor.fetchmany()

        return self._cursor.fetchmany(size)

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def __getattr__(self, name):
        return getattr(self._cursor, name)


# ==================================================
# Connection
# ==================================================

class CompatibleConnection:

    def __init__(self, connection):
        self._connection = connection
        self._closed = False

    def cursor(self):

        if self._closed:
            raise RuntimeError(
                "Database connection is already closed"
            )

        return CompatibleCursor(
            self._connection.cursor()
        )

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):

        if self._closed:
            return

        self._closed = True

        try:
            get_pool().putconn(
                self._connection
            )
        except Exception:

            try:
                self._connection.close()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(
            self._connection,
            name
        )


# ==================================================
# الاتصال بقاعدة البيانات
# ==================================================

def connect():

    pool_instance = get_pool()

    conn = pool_instance.getconn()

    try:

        if conn.closed:
            pool_instance.putconn(
                conn,
                close=True
            )

            conn = pool_instance.getconn()

        return CompatibleConnection(conn)

    except Exception:

        try:
            pool_instance.putconn(
                conn,
                close=True
            )
        except Exception:
            pass

        raise


# ==================================================
# إنشاء الجداول
# ==================================================

def create_tables():

    conn = connect()
    cur = conn.cursor()

    try:

        # ==================================================
        # المستخدمين
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users
        (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            messages INTEGER DEFAULT 0,
            rank TEXT DEFAULT 'عضو',
            joined_date TEXT,
            is_banned INTEGER DEFAULT 0,
            ban_type TEXT DEFAULT '',
            is_muted INTEGER DEFAULT 0,
            mute_type TEXT DEFAULT ''
        )
        """)

        cur.execute("""
        INSERT INTO users
        (
            user_id,
            rank
        )
        VALUES
        (
            8453977662,
            'Dev'
        )
        ON CONFLICT (user_id)
        DO UPDATE SET rank = 'Dev'
        """)

        # ==================================================
        # الردود العادية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS replies
        (
            name TEXT PRIMARY KEY,
            text TEXT,
            type TEXT,
            caption TEXT,
            entities TEXT
        )
        """)

        # ==================================================
        # الردود المميزة
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS special_replies
        (
            name TEXT PRIMARY KEY,
            text TEXT,
            type TEXT,
            caption TEXT,
            entities TEXT
        )
        """)

        # ==================================================
        # النقاط
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS points
        (
            user_id BIGINT PRIMARY KEY,
            points INTEGER DEFAULT 0
        )
        """)

        # ==================================================
        # الألعاب
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS games
        (
            name TEXT PRIMARY KEY,
            image TEXT,
            status TEXT DEFAULT 'on'
        )
        """)

        # ==================================================
        # أسئلة الألعاب
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS game_questions
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            game_name TEXT,
            question TEXT,
            image TEXT,
            caption TEXT,
            answers TEXT
        )
        """)

        # ==================================================
        # إعدادات الألعاب
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS games_settings
        (
            id BIGINT PRIMARY KEY,
            status TEXT DEFAULT 'on'
        )
        """)

        cur.execute("""
        INSERT INTO games_settings
        (
            id,
            status
        )
        VALUES
        (
            1,
            'on'
        )
        ON CONFLICT (id) DO NOTHING
        """)

        # ==================================================
        # سجل الفائزين
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS winners
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            user_id BIGINT,
            game_name TEXT,
            points INTEGER DEFAULT 3,
            date TEXT
        )
        """)

        # ==================================================
        # سلسلة الانتصارات
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS win_streaks
        (
            user_id BIGINT PRIMARY KEY,
            streak INTEGER DEFAULT 0
        )
        """)

        # ==================================================
        # الجوائز اليومية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_rewards
        (
            user_id BIGINT PRIMARY KEY,
            last_reward TEXT
        )
        """)

        # ==================================================
        # الرتب القديمة
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ranks
        (
            user_id BIGINT PRIMARY KEY,
            rank TEXT
        )
        """)

        # ==================================================
        # المشرفين
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS admins
        (
            user_id BIGINT PRIMARY KEY,
            rank TEXT
        )
        """)

        # ==================================================
        # الحظر العام
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS bans
        (
            user_id BIGINT PRIMARY KEY,
            ban_type TEXT DEFAULT 'normal',
            until_time TEXT,
            reason TEXT,
            by_user BIGINT
        )
        """)

        # ==================================================
        # الكتم العام
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS mutes
        (
            user_id BIGINT PRIMARY KEY,
            mute_type TEXT DEFAULT 'normal',
            until_time TEXT,
            reason TEXT,
            by_user BIGINT
        )
        """)

        # ==================================================
        # سجل الإدارة
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS moderation_logs
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            action TEXT,
            user_id BIGINT,
            by_user BIGINT,
            date TEXT
        )
        """)

        # ==================================================
        # السجل الإداري
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            admin_id BIGINT,
            target_id BIGINT,
            action TEXT,
            date TEXT
        )
        """)

        # ==================================================
        # قفل الأوامر
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS command_locks
        (
            command TEXT PRIMARY KEY,
            rank TEXT NOT NULL
        )
        """)

        # ==================================================
        # الأوامر المضافة
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS custom_commands
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            old_command TEXT,
            new_command TEXT UNIQUE
        )
        """)

        # ==================================================
        # المطورين
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS developers
        (
            user_id BIGINT PRIMARY KEY,
            developer_type TEXT NOT NULL DEFAULT 'secondary',
            added_by BIGINT,
            added_date TEXT
        )
        """)

        # ==================================================
        # صلاحيات المطورين
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS developer_permissions
        (
            user_id BIGINT,
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
        # صلاحيات المستخدمين
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions
        (
            user_id BIGINT,
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
            chat_id BIGINT PRIMARY KEY,
            created_date TEXT
        )
        """)

        # ==================================================
        # إعدادات الحماية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS protection_settings
        (
            chat_id BIGINT PRIMARY KEY,

            repetition_enabled INTEGER DEFAULT 0,
            repetition_limit INTEGER DEFAULT 3,
            repetition_seconds INTEGER DEFAULT 5,
            repetition_action TEXT DEFAULT 'mute',

            links_enabled INTEGER DEFAULT 0,
            mentions_enabled INTEGER DEFAULT 0,
            spam_enabled INTEGER DEFAULT 0
        )
        """)

        # =========================================================
        # إعدادات التكرار الإضافية
        # =========================================================

        cur.execute("""
            ALTER TABLE protection_settings
            ADD COLUMN IF NOT EXISTS repetition_warning_duration
            INTEGER DEFAULT 3600
        """)

        cur.execute("""
            ALTER TABLE protection_settings
            ADD COLUMN IF NOT EXISTS repetition_punishment_duration
            INTEGER DEFAULT 300
        """)

        cur.execute("""
            ALTER TABLE protection_settings
            ADD COLUMN IF NOT EXISTS repetition_rank
            TEXT DEFAULT 'عضو'
        """)

        # =========================================================
        # إنذارات التكرار القديمة
        #
        # نبقي الجدول حتى لا يتسبب حذفُه بكسر الملفات القديمة.
        # النظام الجديد سيستخدم جدول warnings.
        # =========================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS repetition_warnings
            (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                warning_id SERIAL PRIMARY KEY,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_repetition_warnings_user
            ON repetition_warnings(chat_id, user_id)
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_repetition_warnings_expiry
            ON repetition_warnings(expires_at)
        """)

        # ==================================================
        # الرتب المتعددة داخل القروب
        #
        # المستخدم يستطيع امتلاك أكثر من رتبة في نفس الوقت.
        #
        # مثال:
        # user_id = 123
        # ادمن
        # ادمن اساسي
        # مميز
        #
        # كل رتبة تكون صفًا مستقلًا.
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS group_user_ranks
        (
            chat_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            rank TEXT NOT NULL,

            PRIMARY KEY
            (
                chat_id,
                user_id,
                rank
            )
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_group_user_ranks_user
        ON group_user_ranks(chat_id, user_id)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_group_user_ranks_rank
        ON group_user_ranks(chat_id, rank)
        """)

        # ==================================================
        # الإنذارات الموحدة
        #
        # كل إنذار يبقى محفوظًا ولا ينتهي تلقائيًا.
        #
        # source:
        # - manual     = أمر انذار
        # - repetition = إنذار التكرار
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS warnings
        (
            chat_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,

            warning_id BIGINT GENERATED BY DEFAULT AS IDENTITY
            PRIMARY KEY,

            source TEXT NOT NULL DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_warnings_user
        ON warnings(chat_id, user_id)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_warnings_created
        ON warnings(chat_id, user_id, created_at)
        """)

        # ==================================================
        # الكلمات المحظورة
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS blocked_words
        (
            chat_id BIGINT,
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
            chat_id BIGINT PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            action TEXT DEFAULT 'mute'
        )
        """)

        # ==================================================
        # رسائل البوت
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_messages
        (
            message_key TEXT PRIMARY KEY,
            message_text TEXT
        )
        """)

        # ==================================================
        # أزرار اللوحات
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS panel_buttons
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,

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
            user_id BIGINT,
            username TEXT
        )
        """)

        # ==================================================
        # المطور الأساسي
        # ==================================================

        cur.execute("""
        INSERT INTO developers
        (
            user_id,
            developer_type
        )
        VALUES
        (
            8453977662,
            'primary'
        )
        ON CONFLICT (user_id) DO NOTHING
        """)

        # ==================================================
        # صلاحيات المستخدمين لكل قروب
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS group_user_permissions
        (
            chat_id BIGINT,
            user_id BIGINT,
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

        # ==================================================
        # ألوان أزرار البوت
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS button_colors
        (
            button_text TEXT PRIMARY KEY,
            color TEXT NOT NULL DEFAULT 'شفاف'
        )
        """)

        # ==================================================
        # إعدادات البداية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS start_settings
        (
            id INTEGER PRIMARY KEY,
            message_text TEXT DEFAULT '',
            message_entities TEXT DEFAULT '[]'
        )
        """)

        cur.execute("""
        INSERT INTO start_settings
        (
            id,
            message_text,
            message_entities
        )
        VALUES
        (
            1,
            '',
            '[]'
        )
        ON CONFLICT (id) DO NOTHING
        """)

        # ==================================================
        # أزرار البداية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS start_buttons
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            button_text TEXT NOT NULL,
            button_url TEXT NOT NULL,
            button_order INTEGER DEFAULT 0
        )
        """)

        # ==================================================
        # صور البداية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS start_images
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            file_id TEXT NOT NULL,
            image_order INTEGER DEFAULT 0
        )
        """)

        # ==================================================
        # صلاحيات البداية
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS start_access
        (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            user_id BIGINT,
            username TEXT
        )
        """)

        # ==================================================
        # إعدادات الإشراف
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS moderation_settings
        (
            chat_id BIGINT PRIMARY KEY,
            durations_enabled INTEGER DEFAULT 0,
            reasons_enabled INTEGER DEFAULT 0
        )
        """)

        # ==================================================
        # كتم البوت
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_mutes
        (
            chat_id BIGINT,
            user_id BIGINT,
            username TEXT,
            first_name TEXT,
            until_time TEXT,
            reason TEXT,
            by_user BIGINT,

            PRIMARY KEY
            (
                chat_id,
                user_id
            )
        )
        """)

        # ==================================================
        # التقييد
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS restrictions
        (
            chat_id BIGINT,
            user_id BIGINT,
            username TEXT,
            first_name TEXT,
            until_time TEXT,
            reason TEXT,
            by_user BIGINT,

            PRIMARY KEY
            (
                chat_id,
                user_id
            )
        )
        """)

        # ==================================================
        # حظر Telegram
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS moderation_bans
        (
            chat_id BIGINT,
            user_id BIGINT,
            username TEXT,
            first_name TEXT,
            until_time TEXT,
            reason TEXT,
            by_user BIGINT,

            PRIMARY KEY
            (
                chat_id,
                user_id
            )
        )
        """)

        # ==================================================
        # فهارس لتحسين البحث
        # ==================================================

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_username
        ON users (username)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_mutes_username
        ON bot_mutes (chat_id, username)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_restrictions_username
        ON restrictions (chat_id, username)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_moderation_bans_username
        ON moderation_bans (chat_id, username)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_moderation_logs_user
        ON moderation_logs (user_id)
        """)

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()
