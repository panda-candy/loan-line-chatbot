"""從環境變數讀取應用程式設定。

專案使用 python-dotenv，因此本機開發可以把密鑰放在 .env 檔。
.env 已被 git 忽略，避免 LINE token 或 MySQL 密碼外洩。
"""

import os
from dotenv import load_dotenv


# 先載入 .env，再讀取 os.getenv，讓本機設定可以覆蓋預設值。
load_dotenv()


class Config:
    """Flask、資料庫與排程模組共用的設定物件。"""

    # LINE 憑證。本機開發時允許空字串，讓 Flask 仍可啟動；
    # 但 /callback 會拒絕 webhook 請求。
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

    # MySQL 連線設定。MYSQL_PORT 轉成 int，因為 PyMySQL 需要數字型 port。
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "loan_chatbot")
    MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")

    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Taipei")

    @property
    def has_line_credentials(self):
        """只有 LINE token 和 secret 都存在時才回傳 True。"""
        return bool(self.LINE_CHANNEL_ACCESS_TOKEN and self.LINE_CHANNEL_SECRET)


# 其他模組直接 import 這個 singleton，避免重複讀取環境變數。
config = Config()
