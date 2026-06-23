"""平台內部信用分數輔助函式。

這不是銀行或官方信用分數，只是根據本系統中借貸專案的還款行為，
計算出的平台內部參考分數。
"""

from datetime import date


# 設定分數上下限，避免加減分後產生不合理數值。
BASE_SCORE = 600
MAX_SCORE = 850
MIN_SCORE = 300


def calculate_credit_score(total_loans=0, paid_on_time=0, overdue_count=0, unpaid_overdue_days=0):
    """依照累積還款行為計算有上下限的信用分數。"""
    score = BASE_SCORE
    # 準時還款會加分，但加分有上限，避免很久以前的行為永久主導分數。
    score += min(paid_on_time * 8, 120)
    score += min(total_loans * 3, 30)
    # 逾期次數與尚未清償的逾期天數會扣分。
    score -= overdue_count * 25
    score -= min(unpaid_overdue_days * 2, 180)
    return max(MIN_SCORE, min(MAX_SCORE, score))


def overdue_days(due_date, paid_at=None, today=None):
    """回傳逾期天數；若未逾期則回傳 0。"""
    today = today or date.today()
    compare_date = paid_at or today
    days = (compare_date - due_date).days
    return max(days, 0)
