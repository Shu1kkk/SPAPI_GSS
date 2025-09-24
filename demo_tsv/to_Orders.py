# get_orders_to_sheet.py
# 毎回TSVを読み込み、シートの Orders タブをヘッダー込みで全置換
# 既存タブは一時タブに入れ替えてから削除（アトミック入れ替え）

import os
import sys
import csv
from datetime import datetime
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# ========= 設定 =========
SHEET_ID   = os.getenv("SHEET_ID", "1RoJeTZpXXaLcbT-cqRCfP3klzRdVfH2CREVTqnSN2Rk")
SHEET_NAME = os.getenv("SHEET_NAME", "Orders")
TSV_PATH   = os.getenv("TSV_PATH", "orders_report.tsv")

# サービスアカウント鍵ファイルの場所
# 1) 環境変数 GOOGLE_APPLICATION_CREDENTIALS を優先
# 2) カレントの service_account.json があればそれを使用
SA_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

# 閲覧中の空白を作らない入れ替え（推奨）
ATOMIC_SWAP = True

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
# ========================


def load_client():
    if not os.path.exists(SA_PATH):
        sys.exit(f"[ERROR] サービスアカウント鍵が見つかりません: {SA_PATH}")

    creds = Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)

    # デバッグ表示
    client_email = creds.service_account_email
    print(f"DEBUG SHEET_ID = {SHEET_ID}")
    print(f"DEBUG client_email = {client_email}")
    return gc


def open_spreadsheet(gc):
    try:
        return gc.open_by_key(SHEET_ID)
    except SpreadsheetNotFound:
        sys.exit(
            "[ERROR] SpreadsheetNotFound (404)\n"
            f"- SHEET_ID: {SHEET_ID}\n"
            "→ スプレッドシートの共有でサービスアカウントに『編集者』権限を付与してください。\n"
            f"→ URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
        )


def get_or_create_worksheet(sh, title, rows=1000, cols=40):
    try:
        return sh.worksheet(title)
    except WorksheetNotFound:
        print(f"[WARN] Worksheet '{title}' not found. Creating...")
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def read_tsv(path):
    if not os.path.exists(path):
        sys.exit(f"[ERROR] TSVが見つかりません: {path}")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        rows = [r for r in reader if len(r) > 0]
    if not rows:
        print("[WARN] TSVが空です。空のまま書き込みます。")
    return rows


def write_full_replace(ws, rows):
    """シンプルにクリア→A1から一括更新（ヘッダー込み）"""
    ws.clear()
    if rows:
        ws.update("A1", rows)
    print(f"✅ wrote {len(rows)} rows (incl. header) to {ws.title}")


def write_full_replace_atomic(sh, target_title, rows):
    """
    アトミック入れ替え：
      1) _tmp へ全書き込み
      2) 旧を削除して _tmp を本番タイトルへリネーム
    """
    # 充分サイズのワークシートを作る
    tmp_title = f"{target_title}_tmp"
    tmp_rows = max(len(rows), 1)
    tmp_cols = max(len(rows[0]) if rows else 1, 1)

    # 既存の _tmp があれば消す
    try:
        old_tmp = sh.worksheet(tmp_title)
        sh.del_worksheet(old_tmp)
    except WorksheetNotFound:
        pass

    ws_tmp = sh.add_worksheet(title=tmp_title, rows=tmp_rows + 10, cols=tmp_cols + 10)
    if rows:
        ws_tmp.update("A1", rows)

    # 既存の本番があれば削除（タイトル競合を避けるため先に消す）
    try:
        ws_old = sh.worksheet(target_title)
        sh.del_worksheet(ws_old)
    except WorksheetNotFound:
        pass

    # _tmp を本番名に
    ws_tmp.update_title(target_title)
    print(f"✅ wrote {len(rows)} rows (incl. header) to {target_title} (atomic swap)")


def run_from_local_tsv():
    rows = read_tsv(TSV_PATH)
    gc = load_client()
    sh = open_spreadsheet(gc)

    if ATOMIC_SWAP:
        write_full_replace_atomic(sh, SHEET_NAME, rows)
    else:
        ws = get_or_create_worksheet(
            sh,
            SHEET_NAME,
            rows=max(len(rows), 1000),
            cols=max(len(rows[0]) if rows else 20, 20),
        )
        write_full_replace(ws, rows)

    print("DONE.")


if __name__ == "__main__":
    try:
        run_from_local_tsv()
    except KeyboardInterrupt:
        print("Interrupted.")
