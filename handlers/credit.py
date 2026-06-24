"""信用紀錄功能 handler。"""


def handle_credit_record(user):
    """顯示平台內信用紀錄。"""
    user_id = user["id"]
    print(f"[MENU] {user_id} -> 信用紀錄")
    # TODO: 未來依還款紀錄計算信用分數。
    return "平台內信用紀錄\n\n信用分數：100\n準時還款率：100%"
