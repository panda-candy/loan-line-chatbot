# LINE ChatBot 雙邊借貸還款提醒與信用紀錄管理系統

## 專案架構

- `app.py`：Flask 主程式與 LINE Webhook。
- `config.py`：讀取 `.env` 環境變數。
- `db.py`：MySQL 連線與交易輔助函式。
- `loan_calculator.py`：貸款金額、利率、期數與還款排程計算。
- `credit_score.py`：平台內信用分數計算。
- `reminder.py`：每日檢查到期與逾期還款。
- `line_messages.py`：LINE 回覆訊息格式。
- `sql/schema.sql`：MySQL 資料表。

## 啟動方式

1. 複製 `.env.example` 為 `.env`，填入 LINE 與 MySQL 設定。
2. 建立 MySQL 資料表：執行 `sql/schema.sql`。
3. 安裝套件：`pip install -r requirements.txt`。
4. 啟動服務：`python app.py`。

LINE Webhook URL 設定為：

```text
https://你的網域/callback
```

## LINE 核心流程

目前支援文字指令版本：

```text
主選單
建立專案
我是借款人
我是放款人
加入專案 邀請碼
我的專案
設定條件 專案ID 金額 年利率 期數 還款方式 還款日
確認條件 專案ID
標記還款 排程ID 金額
確認收款 還款紀錄ID
查詢信用
```

還款方式：

```text
equal_payment
equal_principal
interest_only
bullet
```

## 安全設計

- SQL 查詢集中使用參數化查詢，避免 SQL injection。
- LINE token 與 MySQL 密碼只從 `.env` 讀取，`.env` 不進版本控制。
- `users` 只代表一般 LINE 帳號，不保存固定借款人或放款人身份。
- 借款人/放款人角色綁在每一個 `loan_projects` 專案上，同一人可在不同專案擔任不同角色。
- 專案查詢會限制為建立者、借款人或放款人本人。
- 邀請碼使用 `secrets` 產生 12 位英數隨機碼。
- 附件限制為 JPG、PNG、WebP、PDF，大小上限 10MB，儲存檔名由系統重新產生。
