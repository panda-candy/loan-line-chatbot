from contextlib import contextmanager
import secrets
import string

import pymysql
from pymysql.cursors import DictCursor

from config import config


# 推薦碼前綴使用與平台情境相關、容易辨識的短字。
REFERRAL_PREFIXES = ("PANDA", "USER", "LEND")

# 推薦碼後綴只使用大寫英文字母與數字，方便 LINE 使用者複製與輸入。
REFERRAL_SUFFIX_CHARS = string.ascii_uppercase + string.digits

# 推薦碼長度需求為 6～8 碼。
REFERRAL_MIN_LENGTH = 6
REFERRAL_MAX_LENGTH = 8


def get_connection():
    """建立 MySQL 連線；帳密都從 .env 讀取，不寫死在程式碼。"""
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset=config.MYSQL_CHARSET,
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def db_cursor(commit=False):
    """提供統一的 cursor 與交易處理，避免每個功能重複寫 commit/rollback。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            yield cursor
        if commit:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _generate_referral_candidate():
    """產生一組推薦碼候選值；真正寫入前仍需檢查資料庫是否已存在。"""
    prefix = secrets.choice(REFERRAL_PREFIXES)
    min_suffix_length = max(1, REFERRAL_MIN_LENGTH - len(prefix))
    max_suffix_length = REFERRAL_MAX_LENGTH - len(prefix)
    suffix_length = secrets.choice(range(min_suffix_length, max_suffix_length + 1))
    suffix = "".join(secrets.choice(REFERRAL_SUFFIX_CHARS) for _ in range(suffix_length))
    return f"{prefix}{suffix}"


def _generate_unique_referral_code_with_cursor(cursor, max_attempts=30):
    """在同一個資料庫連線內產生不重複推薦碼，避免重複開連線。"""
    for _ in range(max_attempts):
        referral_code = _generate_referral_candidate()
        cursor.execute(
            "SELECT id FROM users WHERE referral_code = %s LIMIT 1",
            (referral_code,),
        )
        if cursor.fetchone() is None:
            return referral_code
    raise RuntimeError("無法產生唯一推薦碼，請稍後再試。")


def generate_unique_referral_code():
    """產生目前 users 表中尚未使用的 6～8 碼推薦碼。"""
    with db_cursor() as cursor:
        return _generate_unique_referral_code_with_cursor(cursor)


def get_or_create_referral_code(user_id):
    """取得使用者推薦碼；若尚未建立，就自動產生並存入 users.referral_code。"""
    with db_cursor(commit=True) as cursor:
        # FOR UPDATE 會鎖住該使用者資料列，降低同時點擊造成重複建立的機率。
        cursor.execute(
            "SELECT referral_code FROM users WHERE id = %s FOR UPDATE",
            (user_id,),
        )
        user = cursor.fetchone()
        if user is None:
            raise ValueError(f"找不到使用者：{user_id}")

        if user.get("referral_code"):
            return user["referral_code"]

        referral_code = _generate_unique_referral_code_with_cursor(cursor)
        cursor.execute(
            "UPDATE users SET referral_code = %s WHERE id = %s",
            (referral_code, user_id),
        )
        return referral_code
