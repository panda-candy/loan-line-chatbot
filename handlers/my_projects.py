"""我的專案功能 handler。"""


def handle_my_projects(user):
    """顯示目前使用者加入的專案列表。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> 我的專案")
    # TODO: 未來查詢 MySQL projects 與 project_members。
    return "我的專案\n\n目前尚無專案資料"
