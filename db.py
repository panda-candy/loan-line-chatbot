from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from config import config


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
