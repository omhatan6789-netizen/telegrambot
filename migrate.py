import os
import sqlite3
import psycopg2
from psycopg2 import sql

# =========================
# الملفات
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "database.db")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL غير موجود في Environment Variables")

if not os.path.exists(SQLITE_DB):
    raise FileNotFoundError(f"لم يتم العثور على {SQLITE_DB}")


# =========================
# الاتصال
# =========================

sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row

pg_conn = psycopg2.connect(DATABASE_URL)

sqlite_cur = sqlite_conn.cursor()
pg_cur = pg_conn.cursor()


# =========================
# الحصول على الجداول
# =========================

sqlite_cur.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""")

tables = [row["name"] for row in sqlite_cur.fetchall()]

print("الجداول الموجودة:")
for table in tables:
    print(" -", table)

print()
print(f"عدد الجداول: {len(tables)}")


# =========================
# تحويل أنواع SQLite
# =========================

def pg_type(sqlite_type):
    t = (sqlite_type or "").upper()

    if "INT" in t:
        return "BIGINT"

    if "CHAR" in t or "CLOB" in t or "TEXT" in t:
        return "TEXT"

    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return "DOUBLE PRECISION"

    if "BLOB" in t:
        return "BYTEA"

    return "TEXT"


# =========================
# إنشاء الجداول
# =========================

for table in tables:

    print(f"\nإنشاء جدول: {table}")

    sqlite_cur.execute(
        f'PRAGMA table_info("{table}")'
    )

    columns = sqlite_cur.fetchall()

    definitions = []

    primary_keys = []

    for column in columns:

        cid = column["cid"]
        name = column["name"]
        col_type = column["type"]
        not_null = column["notnull"]
        default_value = column["dflt_value"]
        pk = column["pk"]

        definition = [
            sql.Identifier(name),
            sql.SQL(pg_type(col_type))
        ]

        if not_null:
            definition.append(sql.SQL("NOT NULL"))

        if default_value is not None:
            default = str(default_value)

            # تحويل بعض defaults الخاصة بـ SQLite
            if default.upper() == "CURRENT_TIMESTAMP":
                definition.append(sql.SQL("DEFAULT CURRENT_TIMESTAMP"))
            elif default in ("0", "1"):
                definition.append(sql.SQL(f"DEFAULT {default}"))
            elif default.startswith("'") and default.endswith("'"):
                definition.append(
                    sql.SQL("DEFAULT ") + sql.SQL(default)
                )

        definitions.append(sql.SQL(" ").join(definition))

        if pk:
            primary_keys.append((pk, name))

    # ترتيب الـ primary keys
    primary_keys.sort()

    if primary_keys:
        pk_columns = [
            sql.Identifier(name)
            for _, name in primary_keys
        ]

        definitions.append(
            sql.SQL("PRIMARY KEY ({})").format(
                sql.SQL(", ").join(pk_columns)
            )
        )

    create_query = sql.SQL("""
        CREATE TABLE IF NOT EXISTS {} (
            {}
        )
    """).format(
        sql.Identifier(table),
        sql.SQL(", ").join(definitions)
    )

    pg_cur.execute(create_query)


pg_conn.commit()


# =========================
# نقل البيانات
# =========================

print("\n==============================")
print("بدء نقل البيانات")
print("==============================")

for table in tables:

    print(f"\nنقل: {table}")

    sqlite_cur.execute(
        f'SELECT * FROM "{table}"'
    )

    rows = sqlite_cur.fetchall()

    if not rows:
        print("  فارغ، تخطي.")
        continue

    column_names = [
        description[0]
        for description in sqlite_cur.description
    ]

    columns_sql = sql.SQL(", ").join(
        sql.Identifier(column)
        for column in column_names
    )

    placeholders = sql.SQL(", ").join(
        sql.Placeholder()
        for _ in column_names
    )

    insert_query = sql.SQL("""
        INSERT INTO {} ({})
        VALUES ({})
        ON CONFLICT DO NOTHING
    """).format(
        sql.Identifier(table),
        columns_sql,
        placeholders
    )

    inserted = 0

    for row in rows:

        try:
            pg_cur.execute(
                insert_query,
                tuple(row)
            )

            inserted += 1

        except Exception as e:

            print(
                f"  ⚠️ خطأ في جدول {table}: {e}"
            )

            pg_conn.rollback()

            # نعيد إنشاء الاتصال والمعاملة
            pg_cur = pg_conn.cursor()

    pg_conn.commit()

    print(
        f"  تم نقل {inserted} من {len(rows)} سجل"
    )


# =========================
# إصلاح sequences
# =========================

print("\n==============================")
print("إصلاح العدادات")
print("==============================")

for table in tables:

    try:

        sqlite_cur.execute(
            f'PRAGMA table_info("{table}")'
        )

        columns = sqlite_cur.fetchall()

        for column in columns:

            name = column["name"]
            pk = column["pk"]

            if not pk:
                continue

            col_type = (column["type"] or "").upper()

            if "INT" not in col_type:
                continue

            # PostgreSQL sequence
            pg_cur.execute(
                """
                SELECT pg_get_serial_sequence(%s, %s)
                """,
                (table, name)
            )

            result = pg_cur.fetchone()

            if not result or not result[0]:
                continue

            sequence = result[0]

            pg_cur.execute(
                sql.SQL("""
                    SELECT MAX({})
                    FROM {}
                """).format(
                    sql.Identifier(name),
                    sql.Identifier(table)
                )
            )

            max_value = pg_cur.fetchone()[0]

            if max_value is not None:

                pg_cur.execute(
                    """
                    SELECT setval(%s, %s, true)
                    """,
                    (sequence, max_value)
                )

                print(
                    f"  sequence: {table}.{name} -> {max_value}"
                )

    except Exception as e:

        print(
            f"  sequence warning {table}: {e}"
        )

        pg_conn.rollback()

pg_conn.commit()


# =========================
# التحقق
# =========================

print("\n==============================")
print("التحقق من البيانات")
print("==============================")

for table in tables:

    sqlite_cur.execute(
        f'SELECT COUNT(*) FROM "{table}"'
    )

    sqlite_count = sqlite_cur.fetchone()[0]

    pg_cur.execute(
        sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier(table)
        )
    )

    pg_count = pg_cur.fetchone()[0]

    status = "✅" if sqlite_count == pg_count else "⚠️"

    print(
        f"{status} {table}: "
        f"SQLite={sqlite_count} | "
        f"Supabase={pg_count}"
    )


# =========================
# إغلاق
# =========================

sqlite_cur.close()
sqlite_conn.close()

pg_cur.close()
pg_conn.close()

print("\n==============================")
print("✅ انتهى النقل")
print("==============================")