"""借貸專案與還款流程的核心商業邏輯。

本專案最重要的設計規則：
users 不保存全域 borrower/lender 身份。

所有權限判斷都必須依照特定 project 的 loan_project_members.role。
如此同一個 LINE 使用者才能在 A 專案當 borrower，在 B 專案當 lender。
"""

import json
import secrets
import string
from datetime import date

from db import db_cursor
from loan_calculator import build_repayment_schedule


# 邀請碼只用大寫英數，方便 LINE 中複製與輸入。
INVITE_CODE_ALPHABET = string.ascii_uppercase + string.digits
INVITE_CODE_LENGTH = 12


def generate_invite_code():
    """產生不容易被猜到的專案邀請碼。"""
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


def ensure_user(line_user_id, display_name=None):
    """建立或更新 LINE 使用者；users 表不保存固定借款/放款身份。"""
    with db_cursor(commit=True) as cursor:
        # line_user_id 在 users 表中是唯一值。使用 ON DUPLICATE KEY 可以安全處理
        # LINE 對同一個使用者送出重複事件的情況。
        cursor.execute(
            """
            INSERT INTO users (line_user_id, display_name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                display_name = COALESCE(VALUES(display_name), display_name),
                updated_at = CURRENT_TIMESTAMP
            """,
            (line_user_id, display_name),
        )
        cursor.execute("SELECT * FROM users WHERE line_user_id = %s", (line_user_id,))
        return cursor.fetchone()


def set_user_state(user_id, state_key, state_data=None):
    """記錄使用者目前對話狀態，例如正在選擇本專案角色。"""
    # state_data 使用 JSON，之後若加入多步驟輸入流程，可以暫存未完成資料，
    # 不需要為每個暫存欄位都新增資料表欄位。
    payload = json.dumps(state_data or {}, ensure_ascii=False)
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO user_states (user_id, state_key, state_data)
            VALUES (%s, %s, CAST(%s AS JSON))
            ON DUPLICATE KEY UPDATE
                state_key = VALUES(state_key),
                state_data = VALUES(state_data),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, state_key, payload),
        )


def get_user_state(user_id):
    """取得使用者目前對話狀態。"""
    with db_cursor() as cursor:
        cursor.execute("SELECT * FROM user_states WHERE user_id = %s", (user_id,))
        state = cursor.fetchone()
    if state and isinstance(state.get("state_data"), str):
        state["state_data"] = json.loads(state["state_data"])
    return state


def clear_user_state(user_id):
    """清除使用者對話狀態，回到主選單。"""
    with db_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM user_states WHERE user_id = %s", (user_id,))


def get_member_role(project_id, user_id):
    """查詢某位使用者在某個專案中的角色。"""
    # 這是權限判斷的核心來源。不要改成使用 users 上的全域身份欄位。
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT role
            FROM loan_project_members
            WHERE project_id = %s AND user_id = %s
            """,
            (project_id, user_id),
        )
        row = cursor.fetchone()
    return row["role"] if row else None


def require_project_role(project_id, user_id, role):
    """權限檢查：確認使用者在指定專案中具有指定角色。"""
    # 用於需要特定專案角色的操作。若不是專案成員，會和角色錯誤一樣被拒絕。
    if get_member_role(project_id, user_id) != role:
        raise PermissionError(f"only {role} can perform this action")


def create_project(user_id, role):
    """建立專案，並把建立者的角色寫入 loan_project_members。"""
    if role not in {"borrower", "lender"}:
        raise ValueError("role must be borrower or lender")

    for _ in range(5):
        invite_code = generate_invite_code()
        try:
            with db_cursor(commit=True) as cursor:
                # loan_projects 保存邀請碼與專案狀態。
                # 真正的專案角色會在建立專案後，立刻寫入 loan_project_members。
                cursor.execute(
                    """
                    INSERT INTO loan_projects (invite_code, created_by, creator_role, status)
                    VALUES (%s, %s, %s, 'waiting_join')
                    """,
                    (invite_code, user_id, role),
                )
                project_id = cursor.lastrowid

                # 這筆資料代表「user_id 在這個 project 中是 borrower/lender」。
                # UNIQUE KEY (project_id, role) 可避免同一專案出現第二位 borrower
                # 或第二位 lender。
                cursor.execute(
                    """
                    INSERT INTO loan_project_members (project_id, user_id, role)
                    VALUES (%s, %s, %s)
                    """,
                    (project_id, user_id, role),
                )
            return get_project_for_user(project_id, user_id)
        except Exception as exc:
            # invite_code 有 UNIQUE，若真的碰撞就重試。
            if "Duplicate" not in str(exc):
                raise
    raise RuntimeError("could not generate unique invite code")


def join_project_by_invite_code(user_id, invite_code):
    """另一方用邀請碼加入，系統依建立者角色自動指定相對角色。"""
    code = invite_code.strip().upper()
    with db_cursor(commit=True) as cursor:
        # FOR UPDATE 可避免兩個使用者同時使用同一個邀請碼加入，
        # 造成一個專案超過一位 borrower 或 lender。
        cursor.execute(
            """
            SELECT *
            FROM loan_projects
            WHERE invite_code = %s
              AND status = 'waiting_join'
            FOR UPDATE
            """,
            (code,),
        )
        project = cursor.fetchone()
        if not project:
            return None
        if project["created_by"] == user_id:
            raise ValueError("creator cannot join own project")

        # 第二位成員一律會被指定成建立者的相對角色。
        join_role = "borrower" if project["creator_role"] == "lender" else "lender"
        cursor.execute(
            """
            INSERT INTO loan_project_members (project_id, user_id, role)
            VALUES (%s, %s, %s)
            """,
            (project["project_id"], user_id, join_role),
        )
        cursor.execute(
            "UPDATE loan_projects SET status = 'paired' WHERE project_id = %s",
            (project["project_id"],),
        )
    return get_project_for_user(project["project_id"], user_id)


def get_project_for_user(project_id, user_id):
    """只允許專案成員看到自己的專案。"""
    with db_cursor() as cursor:
        # JOIN loan_project_members me 同時負責資料查詢與權限控制。
        # 非專案成員查不到資料，呼叫端可將 None 視為拒絕存取。
        cursor.execute(
            """
            SELECT lp.*,
                   me.role AS current_user_role,
                   borrower.user_id AS borrower_id,
                   lender.user_id AS lender_id
            FROM loan_projects lp
            JOIN loan_project_members me
              ON me.project_id = lp.project_id AND me.user_id = %s
            LEFT JOIN loan_project_members borrower
              ON borrower.project_id = lp.project_id AND borrower.role = 'borrower'
            LEFT JOIN loan_project_members lender
              ON lender.project_id = lp.project_id AND lender.role = 'lender'
            WHERE lp.project_id = %s
            """,
            (user_id, project_id),
        )
        return cursor.fetchone()


def list_projects_for_user(user_id, limit=10):
    """列出使用者參與的專案，以及他在每個專案中的角色。"""
    with db_cursor() as cursor:
        # 從 loan_project_members 開始查詢，結果自然只會包含目前使用者參與的專案。
        cursor.execute(
            """
            SELECT lp.project_id, lp.invite_code, lp.creator_role, lp.status,
                   lp.principal_amount, lp.annual_interest_rate, lp.term_months,
                   lp.repayment_method, lp.repayment_day,
                   me.role AS current_user_role,
                   borrower.user_id AS borrower_id,
                   lender.user_id AS lender_id
            FROM loan_project_members me
            JOIN loan_projects lp ON lp.project_id = me.project_id
            LEFT JOIN loan_project_members borrower
              ON borrower.project_id = lp.project_id AND borrower.role = 'borrower'
            LEFT JOIN loan_project_members lender
              ON lender.project_id = lp.project_id AND lender.role = 'lender'
            WHERE me.user_id = %s
            ORDER BY lp.updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        return cursor.fetchall()


def set_project_terms(user_id, project_id, principal, annual_rate, months, method, repayment_day):
    """放款人設定借貸條件；條件先暫存在 loan_projects，等借款人確認後才成為合約版本。"""
    if method not in {"equal_payment", "equal_principal", "interest_only", "bullet"}:
        raise ValueError("repayment method is not supported")
    if not 1 <= int(repayment_day) <= 31:
        raise ValueError("repayment day must be 1-31")
    # 權限規則：只有這個專案中的 lender 可以設定借貸條件。
    if get_member_role(project_id, user_id) != "lender":
        raise PermissionError("only matched lender can set terms")

    with db_cursor(commit=True) as cursor:
        # 條件會先暫存在 loan_projects。
        # 等 borrower 確認後，才會寫入 contract_versions 成為正式合約版本。
        cursor.execute(
            """
            UPDATE loan_projects
            SET principal_amount = %s,
                annual_interest_rate = %s,
                term_months = %s,
                repayment_method = %s,
                repayment_day = %s,
                status = 'pending_borrower_confirm'
            WHERE project_id = %s
              AND status IN ('paired', 'pending_terms')
              AND (
                  SELECT COUNT(*)
                  FROM loan_project_members
                  WHERE project_id = %s
              ) = 2
            """,
            (principal, annual_rate, months, method, repayment_day, project_id, project_id),
        )
        if cursor.rowcount == 0:
            raise PermissionError("project is not ready for terms")
    return get_project_for_user(project_id, user_id)


def preview_schedule(project):
    """依目前專案條件產生試算排程，不寫入資料庫。"""
    return build_repayment_schedule(
        project["principal_amount"],
        project["annual_interest_rate"],
        project["term_months"],
        start_date=date.today(),
        method=project["repayment_method"],
    )


def activate_contract(user_id, project_id):
    """借款人確認條件後，建立正式合約、合約版本與還款排程。"""
    project = get_project_for_user(project_id, user_id)
    # 權限規則：只有該專案的 borrower 可以接受 lender 提出的條件。
    if not project or project["current_user_role"] != "borrower":
        raise PermissionError("only borrower can accept terms")
    if project["status"] != "pending_borrower_confirm":
        raise ValueError("project is not waiting for borrower confirmation")

    schedule = preview_schedule(project)
    with db_cursor(commit=True) as cursor:
        # loan_contracts 是專案生效後的正式合約資料。
        # 在目前簡化版本中，一個 project 只會有一份合約，因此 project_id 唯一。
        contract_number = f"LC{date.today():%Y%m%d}{secrets.token_hex(4).upper()}"
        cursor.execute(
            """
            INSERT INTO loan_contracts (
                project_id, contract_number, status,
                accepted_by_borrower_at, activated_at
            )
            VALUES (%s, %s, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (project_id, contract_number),
        )
        contract_id = cursor.lastrowid

        # contract_versions 保存借款人接受當下的條件快照。
        # 未來若有條件變更，應新增版本，而不是直接修改舊版本。
        cursor.execute(
            """
            INSERT INTO contract_versions (
                project_id, loan_contract_id, version_no, source_type,
                principal_amount, annual_interest_rate, term_months,
                repayment_method, repayment_day, effective_date, created_by_user_id
            )
            VALUES (%s, %s, 1, 'initial', %s, %s, %s, %s, %s, CURDATE(), %s)
            """,
            (
                project_id,
                contract_id,
                project["principal_amount"],
                project["annual_interest_rate"],
                project["term_months"],
                project["repayment_method"],
                project["repayment_day"],
                user_id,
            ),
        )
        version_id = cursor.lastrowid
        cursor.execute(
            "UPDATE loan_contracts SET current_version_id = %s WHERE id = %s",
            (version_id, contract_id),
        )

        for item in schedule:
            # 儲存依正式合約版本產生的還款排程。
            # 提醒排程會以這些正式資料為準。
            cursor.execute(
                """
                INSERT INTO repayment_schedules (
                    project_id, loan_contract_id, contract_version_id, period_no,
                    due_date, principal_due, interest_due, total_due, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                """,
                (
                    project_id,
                    contract_id,
                    version_id,
                    item["period"],
                    item["due_date"],
                    item["principal"],
                    item["interest"],
                    item["amount_due"],
                ),
            )
        cursor.execute("UPDATE loan_projects SET status = 'active' WHERE project_id = %s", (project_id,))
    return contract_id


def request_amendment(user_id, project_id, reason):
    """放款人可在專案逾期後提出條件變更申請；細部條件之後再逐步擴充。"""
    # 權限規則：只有 lender 可以提出條件變更。
    require_project_role(project_id, user_id, "lender")
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            SELECT id
            FROM loan_contracts
            WHERE project_id = %s AND status = 'active'
            """,
            (project_id,),
        )
        contract = cursor.fetchone()
        if not contract:
            raise ValueError("active contract not found")
        cursor.execute("SELECT status FROM loan_projects WHERE project_id = %s", (project_id,))
        project = cursor.fetchone()
        if not project or project["status"] != "overdue":
            raise PermissionError("amendment can be requested only after overdue")
        # 目前先保留最小變更申請資料。
        # 之後可在不改變角色模型的前提下，加入新的提議條件欄位。
        cursor.execute(
            """
            INSERT INTO amendment_requests (
                project_id, loan_contract_id, requested_by_user_id, reason
            )
            VALUES (%s, %s, %s, %s)
            """,
            (project_id, contract["id"], user_id, reason),
        )
        request_id = cursor.lastrowid
        cursor.execute(
            "UPDATE loan_projects SET status = 'amendment_pending' WHERE project_id = %s",
            (project_id,),
        )
    return request_id


def accept_amendment(user_id, amendment_request_id):
    """借款人接受條件變更申請；目前先記錄接受狀態，後續再產生新版合約。"""
    with db_cursor(commit=True) as cursor:
        # 權限規則：必須透過 loan_project_members 確認使用者是 borrower。
        # 不信任使用者傳入或自行宣稱的角色。
        cursor.execute(
            """
            SELECT ar.*
            FROM amendment_requests ar
            JOIN loan_project_members borrower
              ON borrower.project_id = ar.project_id AND borrower.role = 'borrower'
            WHERE ar.id = %s
              AND borrower.user_id = %s
              AND ar.status = 'pending_borrower_confirm'
            """,
            (amendment_request_id, user_id),
        )
        request_row = cursor.fetchone()
        if not request_row:
            raise PermissionError("amendment request not found for borrower")
        cursor.execute(
            """
            UPDATE amendment_requests
            SET status = 'accepted',
                accepted_at = CURRENT_TIMESTAMP,
                reviewed_by_user_id = %s
            WHERE id = %s
            """,
            (user_id, amendment_request_id),
        )
        cursor.execute(
            "UPDATE loan_projects SET status = 'active' WHERE project_id = %s",
            (request_row["project_id"],),
        )
    return True


def mark_repayment_paid(user_id, schedule_id, paid_amount):
    """借款人標記已還款，等待放款人確認。"""
    with db_cursor(commit=True) as cursor:
        # 權限規則：只有該還款排程所屬 project 的 borrower 可以建立還款紀錄。
        cursor.execute(
            """
            SELECT rs.*, lender.user_id AS lender_id
            FROM repayment_schedules rs
            JOIN loan_project_members borrower
              ON borrower.project_id = rs.project_id AND borrower.role = 'borrower'
            JOIN loan_project_members lender
              ON lender.project_id = rs.project_id AND lender.role = 'lender'
            WHERE rs.id = %s
              AND borrower.user_id = %s
              AND rs.status IN ('pending', 'overdue')
            """,
            (schedule_id, user_id),
        )
        schedule = cursor.fetchone()
        if not schedule:
            raise PermissionError("repayment schedule not found for borrower")

        cursor.execute(
            """
            INSERT INTO repayment_records (
                project_id, repayment_schedule_id, loan_contract_id, payer_user_id,
                receiver_user_id, paid_amount, paid_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                schedule["project_id"],
                schedule_id,
                schedule["loan_contract_id"],
                user_id,
                schedule["lender_id"],
                paid_amount,
            ),
        )
        return cursor.lastrowid


def confirm_repayment(user_id, repayment_record_id):
    """放款人確認收款，並寫入信用分數紀錄。"""
    with db_cursor(commit=True) as cursor:
        # 權限規則：必須透過 loan_project_members.role = lender 確認身份。
        # 不依賴 users 上的全域身份，也不信任呼叫端傳入的身份標籤。
        cursor.execute(
            """
            SELECT rr.*, rs.due_date
            FROM repayment_records rr
            JOIN repayment_schedules rs ON rs.id = rr.repayment_schedule_id
            JOIN loan_project_members lender
              ON lender.project_id = rr.project_id AND lender.role = 'lender'
            WHERE rr.id = %s
              AND lender.user_id = %s
              AND rr.status = 'pending_confirmation'
            """,
            (repayment_record_id, user_id),
        )
        record = cursor.fetchone()
        if not record:
            raise PermissionError("repayment record not found for lender")

        cursor.execute(
            """
            UPDATE repayment_records
            SET status = 'confirmed',
                confirmed_at = CURRENT_TIMESTAMP,
                confirmed_by_user_id = %s
            WHERE id = %s
            """,
            (user_id, repayment_record_id),
        )
        cursor.execute(
            "UPDATE repayment_schedules SET status = 'paid', paid_at = %s WHERE id = %s",
            (record["paid_at"], record["repayment_schedule_id"]),
        )

        event_type = "on_time_payment" if record["paid_at"].date() <= record["due_date"] else "late_payment"
        score_delta = 8 if event_type == "on_time_payment" else -15
        # 信用分數採事件紀錄方式：每次確認收款都新增一筆分數事件，
        # 最新的 score_after 視為目前分數。
        cursor.execute(
            """
            SELECT COALESCE(
                (SELECT score_after FROM credit_scores WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 1),
                600
            ) AS current_score
            """,
            (record["payer_user_id"],),
        )
        score_after = max(300, min(850, int(cursor.fetchone()["current_score"]) + score_delta))
        cursor.execute(
            """
            INSERT INTO credit_scores (
                user_id, project_id, loan_contract_id, repayment_record_id,
                repayment_schedule_id, event_type, score_delta, score_after
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["payer_user_id"],
                record["project_id"],
                record["loan_contract_id"],
                repayment_record_id,
                record["repayment_schedule_id"],
                event_type,
                score_delta,
                score_after,
            ),
        )
    return True


def latest_credit_score(user_id):
    """取得平台內最新信用分數；沒有紀錄時以 600 起算。"""
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT score_after
            FROM credit_scores
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
    return row["score_after"] if row else 600
