# SPAPI_GSS
> Amazon SP-API reports → Google Sheets auto-sync（Python demo / portfolio）  
> ※ **APIキーや実データは含みません。** `.env` と `service_account.json` は各自で用意してください。

---

## 概要
- Amazon Selling Partner API（SP-API）の**注文レポート**を作成 →  **Google スプレッドシートへ転記**します。
- 実データが無い環境でも見た目を確認できるよう、**TSV疑似デモ**も同梱しています。
- いずれも **秘密情報はリポジトリに含めません**（`.env.sample` を参照）。

---

## リポ構成

```text
SPAPI_GSS/
├─ README.md # 本ドキュメント
├─ .gitignore # 秘密情報を除外（.env / *.json など）
├─ .env.sample # ダミー値の雛形（実行者が .env にコピーして実値を入れる）
├─ LICENSE # 例: MIT（任意）
│
├─ demo_spapi/ # 実APIを叩いてシートへ直書きするデモ
│ ├─ spapi_to_sheet_direct.py # LWA → Reports API → DL → Sheets 書き込み
│ └─ spapi-trust.json # 任意: IAMロール trust policy のサンプル（実値は各自置換）
│
├─ demo_tsv/ # 疑似デモ：TSVをシートへ反映して見た目を確認
  ├─ to_Orders.py # ローカルTSVを指定タブへ全置換で反映
  └─ orders_report.tsv # 小さなダミーサンプル（実データではない）
```

---

## セキュリティ方針
- **コードのみ**公開します。**APIトークン／秘密鍵／実データ**は含みません。
- `.gitignore` により `.env` と `*.json` を**常に除外**します。
- 実行したい方は **ご自身のテナント／検証用キー**で `.env` と `service_account.json` を用意してください（本プロジェクトは鍵を一切配布しません）。

---

## 前提・要件
- Python 3.10+  
- Google アカウント / Google スプレッドシート
- （SP-API直書きデモの場合）Amazon SP-API の利用権限、LWAクライアント、AWS署名用の資格情報

### 依存ライブラリ
- pip install python-dotenv requests gspread google-auth
### IAM Role を使う場合のみ
- pip install boto3

### 環境変数（.env）
- .env.sample を .env にコピーし、実値を入力してください。

## 使い方
1) SP-API 直書きデモ（実API）
- 目的：SP-API の注文レポートを作成→ダウンロード→シートへ直接書き込み。
- 実行：
python demo_spapi/spapi_to_sheet_direct.py

出力例：
[INFO] Creating report ...
[INFO] reportId: 50028020354
[DONE] Wrote to sheet: 1FNp... orders_report (existing)
URL: https://docs.google.com/spreadsheets/d/xxxx/edit

2) TSV 疑似デモ（ダミーデータ）
- 目的：実データが無くても、シートに入るとこう見えるを再現。

- 実行：
python demo_tsv/to_Orders.py
入力：demo_tsv/orders_report.tsv（ダミー）
出力：指定タブへ全置換で反映（中途半端な表示を避けるため一時タブ→リネームのアトミック更新を実装）

>鍵が無い状態で実行可能なのは TSV疑似デモ（Googleのサービスアカウントだけ必要）です。

## 補足（ロール運用）
- AWS_ROLE_ARN を使う場合は、ロールの信頼ポリシー（spapi-trust.json 例）に自分のプリンシパルを設定し、ユーザー側にも sts:AssumeRole を付与してください。
- 設定が不完全だと AssumeRole が AccessDenied になります。検証時は直キー→後日ロール切替の順で進めるとトラブルを避けられます。

## 注意
- 本リポジトリは ポートフォリオ公開用 です。
- 実運用する際は、各自の環境と資格情報で実行してください。
- .env と service_account.json は 絶対に公開しないでください。
