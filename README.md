# SPAPI_GSS

Amazon Selling Partner API (SP-API) の注文レポートを取得し、Google スプレッドシートに自動転記する Python デモです。  
このリポジトリは **ポートフォリオ用** です。実際に動作させるには `.env` と `service_account.json` を各自で準備してください。

---

Python スクリプト: TSVを読み取り、Google Sheets APIでシートに書き込み

Google スプレッドシート: 注文一覧が自動で反映される

デモの2パターン
1. SP-API 直書きデモ
demo_spapi/spapi_to_sheet_direct.py

SP-API からレポートを生成 → ダウンロード → シートに直接書き込みます。

実際の取引データが存在する環境で利用可能です。

実行例（ログ抜粋）

csharp
コードをコピーする
[INFO] Creating report ...
[INFO] reportId: 50028020354
[INFO] Writing rows ...
[DONE] Wrote to sheet: 1FNp... orders_report (existing)
URL: https://docs.google.com/spreadsheets/d/xxxx/edit
2. TSV 疑似デモ
demo_tsv/to_Orders.py

ローカルの orders_report.tsv をシートに反映する疑似デモです。

実データがなくても「シートに書き込まれるとこうなる」を確認できます。

サンプルTSVの先頭行

tsv
コードをコピーする
amazon-order-id	merchant-order-id	purchase-date	last-updated-date	order-status
111-2222222-3333333	M-1001	2025-09-20T09:15:00Z	2025-09-21T11:30:00Z	Shipped
シート出力イメージ

セットアップ
Google Drive で空のスプレッドシートを作成し、
service_account.json に記載されたサービスアカウントのメールを「編集者」として共有してください。

.env.sample をコピーして .env を作成し、各自の認証情報を入力してください:

bash
コードをコピーする
cp .env.sample .env
ライブラリをインストール:

bash
コードをコピーする
pip install python-dotenv requests gspread google-auth
# AWS IAM Role を利用する場合のみ
pip install boto3
.gitignore
このリポジトリでは .env や JSON 鍵は 公開しません。
.gitignore には以下を含めてください:

gitignore
コードをコピーする
.env
*.json
注意事項
このリポジトリは ポートフォリオ公開用 です。

実運用する際は、各自で Amazon SP-API / AWS / Google の認証情報を準備してください。

秘密情報（.env, service_account.json など）は 絶対に公開しないでください。
