"""集點優惠第一版。

目前尚未建立正式點數資料表，因此先用固定起始點數與規則文字。
之後可新增 rewards 資料表，再把 get_user_points 改成資料庫查詢。
"""


DEFAULT_POINTS = 0


def get_user_points(user_id):
    """取得使用者目前點數；第一版先回傳固定值。"""
    return DEFAULT_POINTS


def rewards_text(user_id):
    """顯示目前點數與集點規則。"""
    points = get_user_points(user_id)
    return (
        f"集點優惠\n"
        f"目前點數：{points} 點\n\n"
        "集點規則：\n"
        "1. 完成一筆準時還款：+10 點\n"
        "2. 完成一份合約：+20 點\n"
        "3. 發生逾期：暫不加點\n\n"
        "點數兌換功能會在下一版開放。"
    )
