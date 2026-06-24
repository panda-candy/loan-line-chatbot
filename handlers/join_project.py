"""加入專案功能 handler。"""

from loan_service import clear_user_state, set_user_state


def handle_join_project_start(user):
    """開始加入專案流程，要求使用者輸入邀請碼。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> 加入專案")
    set_user_state(user_id, "waiting_invite_code")
    return "請輸入邀請碼"


def handle_invite_code_received(user, invite_code):
    """收到邀請碼後的暫時回覆。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> 輸入邀請碼")
    clear_user_state(user_id)
    # TODO: 未來驗證邀請碼與加入專案。
    return f"收到邀請碼：{invite_code}"
