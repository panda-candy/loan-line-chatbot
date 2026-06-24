"""AI 客服功能 handler。

第一版先使用 rule-based FAQ，不串接真正 AI 服務。
"""


def handle_ai_support(user):
    """顯示可詢問的常見問題。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> AI客服")
    return (
        "AI客服\n\n"
        "你可以詢問：\n"
        "* 如何建立專案\n"
        "* 如何加入專案\n"
        "* 如何還款\n"
        "* 如何查看信用紀錄\n"
        "* 集點優惠怎麼算\n"
        "* 我的推薦碼在哪裡"
    )


def handle_ai_faq(user, user_text):
    """依使用者文字用規則式 FAQ 回覆。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> AI客服 FAQ")
    if "建立專案" in user_text:
        return "建立專案說明：點選「建立專案」，再選擇你在此專案中是借款人或放款人。"
    if "加入專案" in user_text:
        return "加入專案說明：點選「加入專案」，輸入對方提供的邀請碼即可。"
    if "推薦碼" in user_text:
        return (
            "推薦碼說明：點選「集點優惠」即可查看你的專屬推薦碼。"
            "如果你還沒有推薦碼，系統會自動建立一組 6～8 碼推薦碼。"
            "分享給好友加入平台，好友成功註冊後你可獲得 1 點。"
        )
    if "集點" in user_text or "優惠" in user_text or "點數" in user_text:
        return (
            "集點優惠說明：點選「集點優惠」即可查看你的推薦碼。"
            "分享推薦碼給好友，好友成功加入平台可獲得 +1 點；"
            "完成一個借貸專案可獲得 +3 點。"
            "未來點數可用於兌換平台徽章、解鎖進階報表功能與參與平台活動。"
        )
    return handle_ai_support(user)
