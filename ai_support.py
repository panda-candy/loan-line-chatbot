"""第一版 AI 客服：先用 rule-based FAQ 回覆常見問題。

這個檔案目前不串接真正的大型語言模型，目標是先提供穩定、可控、
不會亂回答的客服入口。之後若要接 AI，可以保留這些 FAQ 當作安全 fallback。
"""


FAQ_ITEMS = [
    ("如何建立專案？", "點選「建立專案」，再選擇你在該專案中是借款人或放款人。"),
    ("如何加入專案？", "點選「加入專案」，並輸入對方提供的邀請碼。"),
    ("誰可以設定條件？", "只有該專案中的放款人可以設定金額、利率、期限、還款方式與還款日。"),
    ("誰可以確認條件？", "只有該專案中的借款人可以確認條件，確認後專案才會生效。"),
    ("信用分數怎麼算？", "系統會依照還款紀錄、準時或逾期狀況，計算平台內信用分數。"),
]


def faq_menu_text():
    """回傳 AI 客服第一版可詢問的 FAQ 清單。"""
    lines = ["AI 客服｜常見問題"]
    for index, (question, _) in enumerate(FAQ_ITEMS, start=1):
        lines.append(f"{index}. {question}")
    lines.append("請直接輸入問題關鍵字，例如：如何建立專案")
    return "\n".join(lines)


def answer_faq(user_text):
    """依關鍵字回覆 FAQ；找不到時回傳 FAQ 選單。"""
    normalized = user_text.strip()
    for question, answer in FAQ_ITEMS:
        if normalized in question or question in normalized:
            return answer
    keyword_answers = {
        "建立": FAQ_ITEMS[0][1],
        "加入": FAQ_ITEMS[1][1],
        "設定": FAQ_ITEMS[2][1],
        "確認": FAQ_ITEMS[3][1],
        "信用": FAQ_ITEMS[4][1],
    }
    for keyword, answer in keyword_answers.items():
        if keyword in normalized:
            return answer
    return faq_menu_text()
