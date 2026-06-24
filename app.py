"""Flask 與 LINE Messaging API 的主入口。

這個檔案刻意保持輕量，只負責：
- 驗證 LINE webhook 請求。
- 使用者加入或傳訊息時建立本地 users 紀錄。
- 將 LINE 文字指令導向 loan_service.py 的 helper functions。
- 回傳 LINE 可使用的文字訊息。

借貸專案角色、還款權限等商業規則集中放在 loan_service.py，
這樣不啟動 Flask server 也能測試核心邏輯。
"""

from flask import Flask, abort, request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent

from config import config
from handlers.ai_support import handle_ai_faq, handle_ai_support
from handlers.create_project import handle_create_project_start, handle_project_role_selected
from handlers.credit import handle_credit_record
from handlers.join_project import handle_invite_code_received, handle_join_project_start
from handlers.my_projects import handle_my_projects
from handlers.rewards import handle_rewards
from line_messages import (
    help_text,
    main_menu_message,
    project_summary,
    projects_text,
    schedule_preview_text,
    terms_help_text,
    text_message,
)
from loan_service import (
    activate_contract,
    clear_user_state,
    confirm_repayment,
    create_project,
    ensure_user,
    get_user_state,
    join_project_by_invite_code,
    latest_credit_score,
    list_projects_for_user,
    mark_repayment_paid,
    accept_amendment,
    request_amendment,
    preview_schedule,
    set_project_terms,
    set_user_state,
)
from reminder import start_scheduler
from rewards import rewards_text


app = Flask(__name__)

# LINE SDK 物件集中在這裡初始化；正式 webhook 仍需要 .env 裡的 token/secret。
# 這些物件放在模組層級，符合 LINE SDK 常見用法，也避免每次 webhook
# 事件都重新建立 API client。
line_configuration = Configuration(access_token=config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)
api_client = ApiClient(line_configuration)
line_bot_api = MessagingApi(api_client)
scheduler = start_scheduler(line_bot_api)


@app.get("/")
def health_check():
    # 提供本機與部署平台快速確認 Flask 是否正常啟動。
    return {"status": "ok", "service": "loan-line-chatbot"}


@app.post("/callback")
def callback():
    print("webhook received")

    # 沒有 LINE 憑證時仍可啟動 Flask，但不處理 webhook。
    if not config.has_line_credentials:
        abort(503)

    # LINE 會替 webhook 原始 body 簽章，所以必須把未修改的 raw body
    # 交給 WebhookHandler。若先解析 JSON 或改動空白，簽章驗證可能失敗。
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    print("message event received")

    # 每次收到訊息都先確保 LINE 使用者已存在於 users 表。
    # 這裡不指定 borrower/lender 固定身份。角色是專案層級資料，
    # 只會存放在 loan_project_members。
    user_text = event.message.text.strip()
    print(f"user_text: {user_text}")

    user = ensure_user(event.source.user_id)
    try:
        reply = route_user_message(user, user_text)
    except (ValueError, PermissionError) as exc:
        reply = f"{exc}\n\n{help_text()}"

    if isinstance(reply, str):
        reply = text_message(reply)

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[reply],
        )
    )
    print("reply sent")


@handler.add(FollowEvent)
def handle_follow(event):
    # 使用者加入 LINE Bot 時只建立一般帳號，不詢問固定身份。
    # 使用者只有在建立特定專案時，才會選擇該專案中的 borrower/lender 角色。
    ensure_user(event.source.user_id)
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[main_menu_message()],
        )
    )


def route_user_message(user, user_text):
    # 目前先用文字指令完成流程；之後可替換成 LINE rich menu 或 quick reply。
    # 目前路由保持簡單，之後若改成按鈕或 rich menu，
    # 仍可沿用同一批 loan_service 函式。
    state = get_user_state(user["id"])

    if user_text in {"開始", "主選單", "選單"}:
        clear_user_state(user["id"])
        return main_menu_message()

    if user_text in {"help", "說明", "幫助", "使用說明"}:
        clear_user_state(user["id"])
        return help_text()

    if user_text in {"MENU_CREATE_PROJECT", "建立專案", "建立借貸專案"}:
        return handle_create_project_start(user)

    if user_text in {"MENU_JOIN_PROJECT", "加入專案"}:
        return handle_join_project_start(user)

    if user_text in {"MENU_MY_PROJECTS", "我的專案"}:
        return handle_my_projects(user)

    if user_text in {"MENU_CREDIT_RECORD", "信用紀錄"}:
        return handle_credit_record(user)

    if user_text in {"MENU_AI_SUPPORT", "AI客服", "AI 客服"}:
        set_user_state(user["id"], "awaiting_ai_question")
        return handle_ai_support(user)

    if user_text in {"MENU_REWARDS", "集點優惠"}:
        return handle_rewards(user)

    if state and state["state_key"] == "waiting_invite_code":
        return handle_invite_code_received(user, user_text)

    if state and state["state_key"] == "awaiting_ai_question":
        return handle_ai_faq(user, user_text)

    if user_text in {"我是借款人", "我是放款人"}:
        if not state or state["state_key"] != "waiting_project_role":
            return "請先輸入「建立專案」，再選擇你在該專案中的角色。"
        return handle_project_role_selected(user, user_text)

    if user_text.startswith("加入借貸專案") or user_text.startswith("加入專案"):
        # 用邀請碼加入時，系統會自動指定相對角色：
        # 建立者是 borrower，加入者就是 lender；反之亦然。
        parts = user_text.split()
        if len(parts) != 2:
            return "請輸入：加入借貸專案 邀請碼"
        project = join_project_by_invite_code(user["id"], parts[1])
        if not project:
            return "找不到可加入的專案，請確認邀請碼是否正確或是否已過期。"
        if project["current_user_role"] == "lender":
            return f"配對完成。\n{project_summary(project)}\n\n你是放款人，請輸入「設定條件」。"
        return f"配對完成。\n{project_summary(project)}\n\n請等待放款人設定借貸條件。"

    if user_text == "我的專案":
        return projects_text(list_projects_for_user(user["id"]))

    if user_text == "設定條件":
        return terms_help_text()

    if user_text.startswith("設定條件"):
        # 目前先採用明確的文字格式。未來若改成逐步表單或按鈕，
        # 仍可呼叫同一個 service function。
        parts = user_text.split()
        if len(parts) != 7:
            return terms_help_text()
        _, project_id, principal, annual_rate, months, method, repayment_day = parts
        project = set_project_terms(
            user["id"],
            int(project_id),
            principal,
            annual_rate,
            int(months),
            method,
            int(repayment_day),
        )
        schedule = preview_schedule(project)
        return schedule_preview_text(project, schedule)

    if user_text.startswith("確認條件"):
        # 只有該專案的 borrower 可以啟用合約。loan_service 會先透過
        # loan_project_members.role 檢查權限，再建立還款排程。
        parts = user_text.split()
        if len(parts) != 2:
            return "請輸入：確認條件 專案ID"
        contract_id = activate_contract(user["id"], int(parts[1]))
        return f"合約已生效，合約ID：{contract_id}\n系統已產生正式還款排程。"

    if user_text.startswith("標記還款"):
        # 借款人先標記已還款，放款人再另外確認收款，
        # 避免單方直接把整筆還款標成完成。
        parts = user_text.split()
        if len(parts) != 3:
            return "請輸入：標記還款 排程ID 金額"
        record_id = mark_repayment_paid(user["id"], int(parts[1]), parts[2])
        return f"已送出還款紀錄，等待放款人確認。還款紀錄ID：{record_id}"

    if user_text.startswith("確認收款"):
        # 確認收款會檢查 loan_project_members.role 是否為 lender。
        parts = user_text.split()
        if len(parts) != 2:
            return "請輸入：確認收款 還款紀錄ID"
        confirm_repayment(user["id"], int(parts[1]))
        return "已確認收款，還款紀錄與信用分數已更新。"

    if user_text in {"信用紀錄", "查詢信用"}:
        return f"目前平台內信用分數：{latest_credit_score(user['id'])}"

    if user_text == "AI 客服":
        set_user_state(user["id"], "awaiting_ai_question")
        return faq_menu_text()

    if user_text == "集點優惠":
        return rewards_text(user["id"])

    if user_text.startswith("提出變更"):
        # 條件變更目前保持最小實作：逾期後 lender 可以提出，borrower 可以接受。
        # 產生新版合約版本可作為下一個小步驟再補。
        parts = user_text.split(maxsplit=2)
        if len(parts) != 3:
            return "請輸入：提出變更 專案ID 原因"
        request_id = request_amendment(user["id"], int(parts[1]), parts[2])
        return f"已提出條件變更申請，申請ID：{request_id}，等待借款人接受。"

    if user_text.startswith("接受變更"):
        parts = user_text.split()
        if len(parts) != 2:
            return "請輸入：接受變更 申請ID"
        accept_amendment(user["id"], int(parts[1]))
        return "已接受條件變更申請。"

    return main_menu_message()


if __name__ == "__main__":
    print(f"LINE token loaded: {bool(config.LINE_CHANNEL_ACCESS_TOKEN)}")
    print(f"LINE secret loaded: {bool(config.LINE_CHANNEL_SECRET)}")
    if not config.has_line_credentials:
        print("LINE credentials are not set; Flask will start, but /callback returns 503.")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
