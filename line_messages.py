"""LINE 回覆訊息的文字格式產生器。

把訊息格式集中放在這裡，可避免 app.py 被大量字串模板塞滿。
未來若改成 Flex Message 或 Quick Reply，也能不動商業邏輯。
"""

from linebot.v3.messaging import MessageAction, QuickReply, QuickReplyItem, TextMessage


MAIN_MENU_ACTIONS = [
    ("建立專案", "MENU_CREATE_PROJECT"),
    ("加入專案", "MENU_JOIN_PROJECT"),
    ("我的專案", "MENU_MY_PROJECTS"),
    ("信用紀錄", "MENU_CREDIT_RECORD"),
    ("AI 客服", "MENU_AI_SUPPORT"),
    ("集點優惠", "MENU_REWARDS"),
]


def text_message(text):
    """把純文字包成 LINE SDK 的 TextMessage 物件。"""
    return TextMessage(text=text)


def main_menu_message():
    """建立帶有 Quick Reply 的主選單訊息。"""
    quick_reply_items = [
        QuickReplyItem(action=MessageAction(label=label, text=action_text))
        for label, action_text in MAIN_MENU_ACTIONS
    ]
    return TextMessage(
        text="請選擇功能：",
        quick_reply=QuickReply(items=quick_reply_items),
    )


def main_menu_text():
    """使用者加入 Bot 或要求主選單時顯示的選單文字。"""
    return (
        "主選單\n"
        "建立專案\n"
        "加入專案\n"
        "我的專案\n"
        "信用紀錄\n"
        "AI 客服\n"
        "集點優惠"
    )


def help_text():
    """目前文字指令原型使用的完整指令說明。"""
    return (
        "可用指令：\n"
        "開始 / 主選單\n"
        "建立專案\n"
        "加入專案 邀請碼\n"
        "設定條件 專案ID 金額 年利率 期數 還款方式 還款日\n"
        "確認條件 專案ID\n"
        "標記還款 排程ID 金額\n"
        "確認收款 還款紀錄ID\n"
        "提出變更 專案ID 原因\n"
        "接受變更 申請ID\n"
        "AI 客服\n"
        "集點優惠"
    )


def project_summary(project):
    """產生單一借貸專案的簡短摘要。"""
    # borrower_id/lender_id 是由 loan_service.get_project_for_user
    # 從 loan_project_members 推導出來，不是 users 的全域角色。
    if project.get("lender_id") and project.get("borrower_id"):
        roles = "已配對"
    elif project["creator_role"] == "lender":
        roles = "建立者是放款人，等待借款人加入"
    else:
        roles = "建立者是借款人，等待放款人加入"

    return (
        f"專案ID：{project['project_id']}\n"
        f"邀請碼：{project['invite_code']}\n"
        f"狀態：{project['status']}\n"
        f"專案角色：{roles}"
    )


def projects_text(projects):
    """格式化目前使用者的專案列表，並顯示每個專案中的角色。"""
    if not projects:
        return "目前沒有專案。"
    lines = ["我的專案"]
    for project in projects:
        # current_user_role 是專案層級角色。
        # 同一個使用者可在不同專案中分別是 borrower 或 lender。
        if project.get("current_user_role") == "lender":
            my_role = "放款人"
        elif project.get("current_user_role") == "borrower":
            my_role = "借款人"
        else:
            my_role = "成員"
        terms = "尚未設定條件"
        if project.get("principal_amount") is not None:
            terms = (
                f"{project['principal_amount']} 元 / "
                f"{project['annual_interest_rate']}% / "
                f"{project['term_months']} 期"
            )
        lines.append(f"#{project['project_id']} {my_role} {project['status']} {terms} 邀請碼:{project['invite_code']}")
    return "\n".join(lines)


def schedule_preview_text(project, schedule, max_rows=3):
    """放款人設定條件後，顯示簡短的還款排程試算。"""
    lines = [
        f"專案 #{project['project_id']} 試算排程",
        f"金額：{project['principal_amount']}",
        f"年利率：{project['annual_interest_rate']}%",
        f"期數：{project['term_months']}",
        f"還款方式：{project['repayment_method']}",
    ]
    for item in schedule[:max_rows]:
        # LINE 回覆不宜太長，因此先只顯示前幾期。
        # 完整排程日後可改成分頁指令或更豐富的訊息格式。
        lines.append(f"第 {item['period']} 期 {item['due_date']} 應還 {item['amount_due']}")
    if len(schedule) > max_rows:
        lines.append(f"...共 {len(schedule)} 期")
    lines.append(f"借款人同意請輸入：確認條件 {project['project_id']}")
    return "\n".join(lines)


def terms_help_text():
    """說明目前設定借貸條件的一行文字格式。"""
    return (
        "請用這個格式設定條件：\n"
        "設定條件 專案ID 金額 年利率 期數 還款方式 還款日\n"
        "例如：設定條件 1 10000 3 12 equal_payment 5\n"
        "還款方式：equal_payment、equal_principal、interest_only、bullet"
    )


def role_prompt_text():
    """詢問建立者在這個特定專案中的角色。"""
    return "請選擇你在這個專案中的角色：\n我是借款人\n我是放款人"


def role_prompt_message():
    """用 Quick Reply 詢問建立者在本專案中的角色。"""
    return TextMessage(
        text="請選擇你在這個專案中的角色：",
        quick_reply=QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="我是借款人", text="我是借款人")),
            QuickReplyItem(action=MessageAction(label="我是放款人", text="我是放款人")),
        ]),
    )


def reminder_text(item):
    """格式化每日還款提醒文字。"""
    return (
        f"還款提醒\n"
        f"合約編號：{item['loan_contract_id']}\n"
        f"期數：{item['period_no']}\n"
        f"到期日：{item['due_date']}\n"
        f"應還金額：{item['total_due']}\n"
        f"狀態：{item['status']}"
    )
