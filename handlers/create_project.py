"""建立專案功能 handler。"""

from line_messages import role_prompt_message
from loan_service import clear_user_state, set_user_state


def handle_create_project_start(user):
    """開始建立專案流程，先詢問使用者在此專案中的角色。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> 建立專案")
    set_user_state(user_id, "waiting_project_role")
    return role_prompt_message()


def handle_project_role_selected(user, user_text):
    """使用者選擇本專案角色後的暫時回覆。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> {user_text}")
    clear_user_state(user_id)
    # TODO: 未來建立 project、產生邀請碼、寫入 MySQL。
    return "建立專案功能開發中"
