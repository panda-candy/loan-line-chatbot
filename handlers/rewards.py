"""集點優惠功能 handler。

目前集點優惠包含「我的推薦碼」與介紹好友集點規則。
"""

from db import get_or_create_referral_code


def handle_rewards(user):
    """顯示目前點數、個人推薦碼、介紹好友集點規則與點數用途。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> 集點優惠")
    referral_code = get_or_create_referral_code(user_id)
    # TODO: 未來新用戶註冊時可輸入推薦碼。
    # - 系統查詢推薦人。
    # - 推薦成功後推薦人 +1 點。
    # - 建立 rewards_transactions 紀錄。
    # - 每次點數異動需記錄來源、時間、專案或推薦對象。
    return (
        "集點獎勵計畫\n\n"
        "目前點數：0 點\n\n"
        "你的推薦碼：\n"
        f"{referral_code}\n\n"
        "分享給好友加入平台，\n"
        "好友成功註冊即可獲得 1 點。\n\n"
        "集點規則：\n"
        "• 成功介紹好友加入平台：+1 點\n"
        "• 完成一個借貸專案：+3 點\n\n"
        "點數用途：\n"
        "• 未來可兌換平台徽章\n"
        "• 解鎖進階報表功能\n"
        "• 參與平台活動"
    )
