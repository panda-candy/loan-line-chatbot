"""每日還款提醒與逾期狀態維護。"""

from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from config import config
from db import db_cursor


def find_due_repayments(days_ahead=1):
    """找出即將到期或已逾期的還款排程，並帶出 LINE 接收者。"""
    target_date = date.today() + timedelta(days=days_ahead)
    with db_cursor() as cursor:
        # borrower 與 lender 透過 loan_project_members 查出，不使用 users 角色欄位。
        # 這能確保提醒符合「專案層級角色」設計。
        cursor.execute(
            """
            SELECT rs.*,
                   borrower.line_user_id AS borrower_line_user_id,
                   lender.line_user_id AS lender_line_user_id
            FROM repayment_schedules rs
            JOIN loan_project_members borrower_member
              ON borrower_member.project_id = rs.project_id
             AND borrower_member.role = 'borrower'
            JOIN loan_project_members lender_member
              ON lender_member.project_id = rs.project_id
             AND lender_member.role = 'lender'
            JOIN users borrower ON borrower.id = borrower_member.user_id
            JOIN users lender ON lender.id = lender_member.user_id
            WHERE rs.status IN ('pending', 'overdue')
              AND rs.due_date <= %s
            ORDER BY rs.due_date ASC
            """,
            (target_date,),
        )
        return cursor.fetchall()


def mark_overdue_repayments():
    """將逾期的還款排程與其專案標記為 overdue。"""
    with db_cursor(commit=True) as cursor:
        # 先更新已超過到期日的還款排程。
        cursor.execute(
            """
            UPDATE repayment_schedules
            SET status = 'overdue'
            WHERE status = 'pending'
              AND due_date < CURDATE()
            """
        )
        overdue_count = cursor.rowcount
        # 再把專案狀態同步成 overdue，讓後續條件變更流程可以啟用。
        cursor.execute(
            """
            UPDATE loan_projects lp
            SET lp.status = 'overdue'
            WHERE lp.status = 'active'
              AND EXISTS (
                  SELECT 1
                  FROM repayment_schedules rs
                  WHERE rs.project_id = lp.project_id
                    AND rs.status = 'overdue'
              )
            """
        )
        return overdue_count


def daily_repayment_check(line_bot_api=None):
    """執行每日逾期更新，並視情況推送 LINE 提醒。"""
    mark_overdue_repayments()
    due_items = find_due_repayments(days_ahead=1)

    if line_bot_api is None:
        # 沒有傳入 LINE API 時直接回傳資料，方便測試時不真的推播。
        return due_items

    from linebot.v3.messaging import PushMessageRequest

    from line_messages import reminder_text, text_message

    for item in due_items:
        # 同時通知 borrower 和 lender，讓雙方看到一致的到期/逾期資訊。
        for user_id in {item["borrower_line_user_id"], item["lender_line_user_id"]}:
            if user_id:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[text_message(reminder_text(item))],
                    )
                )
    return due_items


def start_scheduler(line_bot_api=None):
    """啟動 APScheduler 背景排程，每日檢查還款狀態。"""
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        daily_repayment_check,
        "cron",
        hour=9,
        minute=0,
        args=[line_bot_api],
        id="daily_repayment_check",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
