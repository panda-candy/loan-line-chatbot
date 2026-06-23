"""借貸還款試算工具。

這個檔案刻意不依賴資料庫，因此可以重複用於：
- 借款人確認前的試算排程。
- 合約生效後的正式還款排程。
- 還款計算的單元測試。
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP


# 金額使用 Decimal 並四捨五入到小數點後兩位，避免 float 精度造成排程誤差。
TWOPLACES = Decimal("0.01")


def money(value):
    """將數值標準化成小數點後兩位的 Decimal 金額。"""
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def add_months(start_date, months):
    """增加指定月數，同時處理月底日期不合法的情況。"""
    year = start_date.year + (start_date.month - 1 + months) // 12
    month = (start_date.month - 1 + months) % 12 + 1
    month_lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(start_date.day, month_lengths[month - 1])
    return date(year, month, day)


def calculate_equal_payment(principal, annual_rate, months):
    """計算本息平均攤還的固定每月付款金額。"""
    principal = Decimal(str(principal))
    monthly_rate = Decimal(str(annual_rate)) / Decimal("100") / Decimal("12")

    if months <= 0:
        raise ValueError("months must be greater than 0")
    if monthly_rate == 0:
        # 若利率為 0%，每期金額就是本金平均分攤。
        return money(principal / Decimal(months))

    factor = (Decimal("1") + monthly_rate) ** months
    payment = principal * monthly_rate * factor / (factor - Decimal("1"))
    return money(payment)


def build_repayment_schedule(principal, annual_rate, months, start_date=None, method="equal_payment"):
    """依指定還款方式建立還款排程。"""
    if start_date is None:
        start_date = date.today()

    principal = Decimal(str(principal))
    monthly_rate = Decimal(str(annual_rate)) / Decimal("100") / Decimal("12")
    remaining = principal
    schedule = []

    if method not in {"equal_payment", "equal_principal", "interest_only", "bullet"}:
        raise ValueError("method must be equal_payment, equal_principal, interest_only, or bullet")

    payment = calculate_equal_payment(principal, annual_rate, months) if method == "equal_payment" else None
    principal_part_fixed = money(principal / Decimal(months)) if method == "equal_principal" else None

    for period in range(1, months + 1):
        interest = money(remaining * monthly_rate)

        if method == "equal_payment":
            # 本息平均攤還：每期總額固定，本金占比逐期增加。
            principal_part = money(payment - interest)
            total_payment = payment
        elif method == "equal_principal":
            # 本金平均攤還：每期本金固定，總還款額逐期下降。
            principal_part = principal_part_fixed
            total_payment = money(principal_part + interest)
        elif method == "interest_only":
            # 只繳利息：每期繳利息，最後一期繳清本金。
            principal_part = Decimal("0.00")
            total_payment = interest
        else:
            # 到期一次清償：最後一期才繳本金與利息。
            principal_part = Decimal("0.00")
            total_payment = Decimal("0.00")

        if period == months:
            # 最後一期一定清掉剩餘本金，避免多期四捨五入後留下極小尾差。
            principal_part = money(remaining)
            total_payment = money(principal_part + interest)

        remaining = money(remaining - principal_part)
        schedule.append({
            "period": period,
            "due_date": add_months(start_date, period),
            "principal": principal_part,
            "interest": interest,
            "amount_due": total_payment,
            "remaining_principal": max(remaining, Decimal("0.00")),
        })

    return schedule
