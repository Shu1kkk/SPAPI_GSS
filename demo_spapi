# spapi_to_sheet_direct.py
# -*- coding: utf-8 -*-
"""
SP-API の注文レポートを作成→ダウンロード→Googleスプレッドシートへ書き込む
- .env を明示ロード（python-dotenv）
- 命名ゆれのある .env キーを期待キーへ自動マッピング（エイリアス補完）
- 新規スプレッドシートは「作成しない」（SHEET_ID必須）で容量/権限トラブルを回避
- gspread worksheet.update は values を先、range_name は named 引数（DeprecationWarning解消）
- ヘッダー固定、事前クリア、チャンク更新付き
"""

import os
import io
import csv
import sys
import json
import time
import math
import gzip
import hmac
import hashlib
import datetime as dt
from urllib.parse import urlencode

import requests
from google.oauth2.service_account import Credentials
import gspread

# === .env ロード & エイリアス補完 ============================================
from dotenv import load_dotenv
import pathlib

# スクリプトと同じフォルダの .env を読み込む（必要ならパス調整可）
env_path = pathlib.Path(__file__).with_name(".env")
load_dotenv(dotenv_path=str(env_path), override=False)

def _set_if_missing(target_key: str, candidates: list[str]):
    """target_key が未設定なら、候補のうち最初に見つかった値で補完"""
    if os.getenv(target_key):
        return
    for c in candidates:
        v = os.getenv(c)
        if v and str(v).strip():
            os.environ[target_key] = v
            break

# LWA / SP-API（あなたの .env のキー名揺れに対応）
_set_if_missing("SPAPI_CLIENT_ID",     ["LWA_CLIENT_ID", "LWA_APP_ID"])
_set_if_missing("SPAPI_CLIENT_SECRET", ["LWA_CLIENT_SECRET"])
# AWS
_set_if_missing("AWS_ACCESS_KEY_ID",     ["AWS_ACCESS_KEY"])
_set_if_missing("AWS_SECRET_ACCESS_KEY", ["AWS_SECRET_KEY"])
_set_if_missing("SPAPI_ROLE_ARN",        ["AWS_ROLE_ARN"])
# Google
_set_if_missing("SERVICE_ACCOUNT_JSON",  ["GOOGLE_SERVICE_ACCOUNT_JSON"])
# マーケット（未設定ならJPを既定化）
if not os.getenv("MARKETPLACE_IDS"):
    os.environ["MARKETPLACE_IDS"] = "A1VC38T7YXB528"
# ===========================================================================

# -----------------------------
# 設定ユーティリティ
# -----------------------------

def env(key, default=None, required=False):
    v = os.getenv(key, default)
    if required and (v is None or str(v).strip() == ""):
        raise RuntimeError(f"環境変数が未設定: {key}")
    return v

def now_utc_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def iso_minus_days(days: int):
    return (dt.datetime.utcnow().replace(microsecond=0) - dt.timedelta(days=days)).isoformat() + "Z"

def print_info(msg): print(f"[INFO] {msg}")
def print_warn(msg): print(f"[WARN] {msg}")
def print_done(msg): print(f"[DONE] {msg}")

# -----------------------------
# LWA トークン
# -----------------------------

def get_lwa_access_token():
    client_id     = env("SPAPI_CLIENT_ID", required=True)
    client_secret = env("SPAPI_CLIENT_SECRET", required=True)
    refresh_token = env("SPAPI_REFRESH_TOKEN", required=True)

    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    r = requests.post(url, data=data, timeout=60)
    r.raise_for_status()
    tok = r.json()["access_token"]
    return tok

# -----------------------------
# AWS SigV4 署名（最小実装）
# -----------------------------

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, regionName, serviceName):
    # 署名キーの各段は bytes を使う
    kDate = hmac.new(("AWS4" + key).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
    kRegion = hmac.new(kDate, regionName.encode("utf-8"), hashlib.sha256).digest()
    kService = hmac.new(kRegion, serviceName.encode("utf-8"), hashlib.sha256).digest()  # ← ここを修正
    kSigning = hmac.new(kService, b"aws4_request", hashlib.sha256).digest()
    return kSigning


def aws_sigv4_headers(method, service, region, host, uri, querystring, payload, access_key, secret_key, security_token=None):
    t = dt.datetime.utcnow()
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = t.strftime("%Y%m%d")

    canonical_uri = uri
    canonical_querystring = querystring
    canonical_headers = f"host:{host}\n" + f"x-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-date"
    if security_token:
        canonical_headers += f"x-amz-security-token:{security_token}\n"
        signed_headers += ";x-amz-security-token"

    payload_bytes = payload if isinstance(payload, (bytes, bytearray)) else payload.encode("utf-8")
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    canonical_request = "\n".join([
        method,
        canonical_uri,
        canonical_querystring,
        canonical_headers,
        signed_headers,
        payload_hash
    ])

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        algorithm,
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    ])
    signing_key = get_signature_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization_header = f"{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    headers = {
        "x-amz-date": amz_date,
        "Authorization": authorization_header,
        "host": host,
    }
    if security_token:
        headers["x-amz-security-token"] = security_token
    return headers

# -----------------------------
# STS 一時認証（任意：ROLEを使う場合）
# -----------------------------

def get_aws_credentials():
    ak = env("AWS_ACCESS_KEY_ID", required=True)
    sk = env("AWS_SECRET_ACCESS_KEY", required=True)
    st = os.getenv("AWS_SESSION_TOKEN")  # 任意
    role_arn = os.getenv("SPAPI_ROLE_ARN")  # 任意

    if role_arn:
        try:
            import boto3
        except Exception:
            raise RuntimeError("SPAPI_ROLE_ARN が設定されています。boto3 をインストールするか、ROLEを外してください。")

        sts = boto3.client(
            "sts",
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            aws_session_token=st,
            region_name=env("AWS_REGION", "us-west-2")
        )
        resp = sts.assume_role(RoleArn=role_arn, RoleSessionName="spapi-session")
        creds = resp["Credentials"]
        return creds["AccessKeyId"], creds["SecretAccessKey"], creds["SessionToken"]

    return ak, sk, st

# -----------------------------
# SP-API: レポート作成→ポーリング→ドキュメントURL
# -----------------------------

SPAPI_HOST_BY_REGION = {
    "na": "sellingpartnerapi-na.amazon.com",
    "eu": "sellingpartnerapi-eu.amazon.com",
    "fe": "sellingpartnerapi-fe.amazon.com",
}
# 日本は "fe"
def region_host():
    return "fe", SPAPI_HOST_BY_REGION["fe"]

def create_report(lwa_token, aws_ak, aws_sk, aws_sess, report_type, marketplace_ids, data_start, data_end):
    region_code, host = region_host()
    region_sign = env("AWS_REGION", "us-west-2")
    service = "execute-api"

    url_path = "/reports/2021-06-30/reports"
    url_qs = ""
    body = {
        "reportType": report_type,
        "marketplaceIds": marketplace_ids,
        "dataStartTime": data_start,
        "dataEndTime": data_end
    }
    payload = json.dumps(body)
    headers = {
        "content-type": "application/json",
        "x-amz-access-token": lwa_token,
    }
    sig_headers = aws_sigv4_headers(
        method="POST", service=service, region=region_sign,
        host=host, uri=url_path, querystring=url_qs, payload=payload,
        access_key=aws_ak, secret_key=aws_sk, security_token=aws_sess
    )
    headers.update(sig_headers)
    resp = requests.post(f"https://{host}{url_path}", headers=headers, data=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["reportId"]

def get_report(lwa_token, aws_ak, aws_sk, aws_sess, report_id):
    region_code, host = region_host()
    region_sign = env("AWS_REGION", "us-west-2")
    service = "execute-api"

    url_path = f"/reports/2021-06-30/reports/{report_id}"
    url_qs = ""
    payload = ""
    headers = {
        "x-amz-access-token": lwa_token,
    }
    sig_headers = aws_sigv4_headers(
        method="GET", service=service, region=region_sign,
        host=host, uri=url_path, querystring=url_qs, payload=payload,
        access_key=aws_ak, secret_key=aws_sk, security_token=aws_sess
    )
    headers.update(sig_headers)
    resp = requests.get(f"https://{host}{url_path}", headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()

def get_document(lwa_token, aws_ak, aws_sk, aws_sess, doc_id):
    region_code, host = region_host()
    region_sign = env("AWS_REGION", "us-west-2")
    service = "execute-api"

    url_path = f"/reports/2021-06-30/documents/{doc_id}"
    url_qs = ""
    payload = ""
    headers = {
        "x-amz-access-token": lwa_token,
    }
    sig_headers = aws_sigv4_headers(
        method="GET", service=service, region=region_sign,
        host=host, uri=url_path, querystring=url_qs, payload=payload,
        access_key=aws_ak, secret_key=aws_sk, security_token=aws_sess
    )
    headers.update(sig_headers)
    resp = requests.get(f"https://{host}{url_path}", headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()  # {url, compressionAlgorithm?}

def wait_report_done(*, lwa_token, aws_ak, aws_sk, aws_sess, report_id, timeout_sec=600, poll_interval=5):
    print_info("Waiting report DONE ...")
    t0 = time.time()
    while True:
        meta = get_report(lwa_token, aws_ak, aws_sk, aws_sess, report_id)
        status = meta.get("processingStatus")
        if status in ("DONE", "FATAL"):
            return meta
        if time.time() - t0 > timeout_sec:
            raise TimeoutError(f"Report not DONE in {timeout_sec} sec (last status={status})")
        time.sleep(poll_interval)

def download_report_from_presigned(url: str, compression: str | None):
    print_info("Getting presigned url ...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    content = r.content
    if compression and compression.upper() == "GZIP":
        content = gzip.decompress(content)
    return content.decode("utf-8", errors="replace")

# -----------------------------
# TSV → 2次元配列
# -----------------------------

def tsv_to_rows(tsv_text: str):
    reader = csv.reader(io.StringIO(tsv_text), delimiter="\t")
    return [row for row in reader]

# -----------------------------
# Google Sheets
# -----------------------------

def gspread_client(service_json_path: str):
    if not os.path.exists(service_json_path):
        raise FileNotFoundError(f"service_account.json が見つかりません: {service_json_path}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(service_json_path, scopes=scopes)
    return gspread.authorize(creds)

def open_or_create_ws(service_json_path: str, sheet_id: str, sheet_tab: str):
    """
    スプレッドシート本体の「新規作成」はしない（SHEET_ID必須）。
    指定タブがなければ作成する。
    """
    print_info("Opening/creating spreadsheet ...")
    gc = gspread_client(service_json_path)
    sh = gc.open_by_key(sheet_id)  # 所有はユーザー側。SAは「編集者」で共有されている前提
    try:
        ws = sh.worksheet(sheet_tab)
        created = False
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_tab, rows=100, cols=26)
        created = True
    return ws, sh.id, created

def a1(r, c):
    # 1-indexed → A1
    letters = ""
    while c > 0:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{r}"

def write_rows(ws, rows, *, clear_before=True, freeze_header=True, chunk_rows=1000):
    if clear_before:
        ws.clear()

    if not rows:
        ws.update([[]], range_name="A1", value_input_option="RAW")
        return

    r0, c0 = 1, 1
    total = len(rows)
    CH = max(1, chunk_rows)
    for i in range(0, total, CH):
        block = rows[i:i+CH]
        start_row = r0 + i
        end_row = start_row + len(block) - 1
        width = max(len(r) for r in block) if block else 1
        start_col = c0
        end_col = c0 + max(1, width) - 1

        # values を先、range_name は named 引数
        ws.update(
            block,
            range_name=f"{a1(start_row, start_col)}:{a1(end_row, end_col)}",
            value_input_option="RAW"
        )

    if freeze_header and len(rows) > 0:
        try:
            ws.freeze(rows=1)
        except Exception:
            pass

# -----------------------------
# メイン
# -----------------------------

def main():
    # 窓期間（最大30日）
    window_days = int(env("WINDOW_DAYS", "30"))
    if window_days > 30:
        window_days = 30

    data_end = now_utc_iso()
    data_start = iso_minus_days(window_days)
    print_info(f"window UTC: {data_start} → {data_end}")

    # レポート種別
    basis = env("REPORT_BASIS", "LAST_UPDATE").upper().strip()
    if basis not in ("LAST_UPDATE", "ORDER_DATE"):
        basis = "LAST_UPDATE"

    if basis == "LAST_UPDATE":
        report_type = "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_LAST_UPDATE_GENERAL"
    else:
        report_type = "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL"

    # マーケット
    mkt_raw = env("MARKETPLACE_IDS", None, required=False)
    if not mkt_raw or not mkt_raw.strip():
        print_warn("MARKETPLACE_IDS が未設定のため日本(JP)を既定値として使用します: A1VC38T7YXB528")
        mkt_raw = "A1VC38T7YXB528"
    mkt = [s.strip() for s in mkt_raw.split(",") if s.strip()]

    # Google Sheets
    sheet_id = env("SHEET_ID", required=True).strip()
    sheet_tab = env("SHEET_TAB", "orders_report").strip()
    service_json = env("SERVICE_ACCOUNT_JSON", "./service_account.json").strip()

    print_info("Requesting LWA access token ...")
    lwa = get_lwa_access_token()

    # AWS 資格情報
    ak, sk, sess = get_aws_credentials()

    print_info("Creating report ...")
    report_id = create_report(
        lwa_token=lwa,
        aws_ak=ak, aws_sk=sk, aws_sess=sess,
        report_type=report_type,
        marketplace_ids=mkt,
        data_start=data_start,
        data_end=data_end
    )
    print_info(f"reportId: {report_id}")

    meta = wait_report_done(lwa_token=lwa, aws_ak=ak, aws_sk=sk, aws_sess=sess, report_id=report_id)
    status = meta.get("processingStatus")
    if status != "DONE":
        raise RuntimeError(f"Report status not DONE: {status}")

    doc_id = meta.get("reportDocumentId")
    print_info(f"reportDocumentId: {doc_id}")

    doc = get_document(lwa_token=lwa, aws_ak=ak, aws_sk=sk, aws_sess=sess, doc_id=doc_id)
    url = doc.get("url")
    comp = doc.get("compressionAlgorithm")
    print_info(f"download url obtained (compression={comp})")

    tsv_text = download_report_from_presigned(url, comp)
    rows = tsv_to_rows(tsv_text)

    print(f"DEBUG SHEET_ID = '{sheet_id}'")
    print(f"DEBUG JSON PATH = {os.path.abspath(service_json)} exists? {os.path.exists(service_json)}")
    # サービスアカウントメールをログ
    try:
        with open(service_json, "r", encoding="utf-8") as f:
            sa = json.load(f)
            print(f"DEBUG SA EMAIL = {sa.get('client_email')}")
    except Exception:
        pass

    ws, final_sheet_id, created = open_or_create_ws(service_json, sheet_id, sheet_tab)
    print_info("Writing rows ...")
    write_rows(ws, rows, clear_before=True, freeze_header=True, chunk_rows=1000)

    print_done(f"Wrote to sheet: {final_sheet_id} {sheet_tab} ({'created' if created else 'existing'})")
    print(f"URL: https://docs.google.com/spreadsheets/d/{final_sheet_id}/edit")

    # 簡易プレビュー
    if rows:
        preview_cols = min(8, max(1, len(rows[0])))
        header_sample = "\t".join(rows[0][:preview_cols])
        print("----- preview -----")
        print(header_sample)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
