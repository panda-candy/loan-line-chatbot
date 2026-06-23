"""附件檔案驗證輔助函式。

資料庫約束可以保護已寫入的檔案 metadata，但上傳程式在儲存檔案前
仍應先做應用層驗證。這些函式就是應用層檢查。
"""

from pathlib import Path
from uuid import uuid4


# 允許的 MIME type，以及系統儲存時使用的副檔名。
# 實際儲存檔名由系統產生，不信任使用者原始檔名。
ALLOWED_ATTACHMENT_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024


def validate_attachment(file_name, mime_type, size_bytes):
    """接受上傳前，檢查檔案類型、大小與副檔名。"""
    # MIME type 必須在安全白名單中。
    if mime_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise ValueError("unsupported attachment type")
    # 必須提供檔案大小，否則無法可靠執行大小上限。
    if size_bytes is None or int(size_bytes) <= 0:
        raise ValueError("attachment size is required")
    if int(size_bytes) > MAX_ATTACHMENT_SIZE_BYTES:
        raise ValueError("attachment is too large")

    expected_suffix = ALLOWED_ATTACHMENT_MIME_TYPES[mime_type]
    original_suffix = Path(file_name).suffix.lower()
    # 如果原始檔名有副檔名，要求它必須與 MIME type 對應。
    # 這不能取代檔案內容檢查，但可擋掉明顯不一致的檔案。
    if original_suffix and original_suffix != expected_suffix:
        raise ValueError("attachment extension does not match content type")
    return True


def safe_attachment_name(mime_type):
    """替已驗證的 MIME type 產生隨機儲存檔名。"""
    if mime_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise ValueError("unsupported attachment type")
    return f"{uuid4().hex}{ALLOWED_ATTACHMENT_MIME_TYPES[mime_type]}"
