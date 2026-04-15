"""매일 아침 텔레그램으로 '클로드 to do' 시트 요약 발송.
- 대기 항목만 별점순 나열
- 3일 이상 완료된 항목 자동 정리(별도 탭 '완료 아카이브'로 이동)
"""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TODO_CHAT_ID"]
SHEET_ID = os.environ["SHEET_ID"]
GA_TOKEN_PATH = "/Users/sanghun/ga_token.json"
GA_CLIENT_ID = os.environ.get("GA_CLIENT_ID")
GA_CLIENT_SECRET = os.environ.get("GA_CLIENT_SECRET")
GA_REFRESH_TOKEN = os.environ.get("GA_REFRESH_TOKEN")
SHEET_TAB = "클로드 to do"
ARCHIVE_TAB = "완료 아카이브"

def get_sheet_id(tok, title):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}?fields=sheets.properties"
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}))
    for s in json.loads(r.read())['sheets']:
        if s['properties']['title'] == title:
            return s['properties']['sheetId']
    return None

def apply_priority_colors(tok, keep):
    """⭐⭐⭐⭐⭐ 최우선=빨강+볼드, 회신대기=초록, 나머지 기본색."""
    sid = get_sheet_id(tok, SHEET_TAB)
    if sid is None: return
    n = len(keep) + 1
    reqs = [{
        "repeatCell":{
            "range":{"sheetId":sid,"startRowIndex":1,"endRowIndex":n,"startColumnIndex":0,"endColumnIndex":7},
            "cell":{"userEnteredFormat":{"textFormat":{"foregroundColor":{"red":0,"green":0,"blue":0},"bold":False}}},
            "fields":"userEnteredFormat.textFormat(foregroundColor,bold)"
        }
    }]
    for i, r in enumerate(keep, start=1):
        status = (r+[""]*7)[1]
        if status == "회신대기":
            reqs.append({
                "repeatCell":{
                    "range":{"sheetId":sid,"startRowIndex":i,"endRowIndex":i+1,"startColumnIndex":0,"endColumnIndex":7},
                    "cell":{"userEnteredFormat":{"textFormat":{"foregroundColor":{"red":0.13,"green":0.55,"blue":0.23},"bold":False}}},
                    "fields":"userEnteredFormat.textFormat(foregroundColor,bold)"
                }
            })
        elif stars_count(r[2]) == 5:
            reqs.append({
                "repeatCell":{
                    "range":{"sheetId":sid,"startRowIndex":i,"endRowIndex":i+1,"startColumnIndex":0,"endColumnIndex":7},
                    "cell":{"userEnteredFormat":{"textFormat":{"foregroundColor":{"red":0.86,"green":0.15,"blue":0.15},"bold":True}}},
                    "fields":"userEnteredFormat.textFormat(foregroundColor,bold)"
                }
            })
    urllib.request.urlopen(urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}:batchUpdate",
        data=json.dumps({"requests":reqs}).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type":"application/json"}))

def token():
    if GA_CLIENT_ID and GA_CLIENT_SECRET and GA_REFRESH_TOKEN:
        cid, csec, rtok = GA_CLIENT_ID, GA_CLIENT_SECRET, GA_REFRESH_TOKEN
    else:
        with open(GA_TOKEN_PATH) as f: td = json.load(f)
        cid, csec, rtok = td['client_id'], td['client_secret'], td['refresh_token']
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": csec,
        "refresh_token": rtok, "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data)).read())['access_token']

def sheets_read(tok, rng):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{urllib.parse.quote(rng)}"
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"}))
    return json.loads(r.read()).get('values', [])

def sheets_put(tok, rng, values):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{urllib.parse.quote(rng)}?valueInputOption=USER_ENTERED"
    urllib.request.urlopen(urllib.request.Request(url, data=json.dumps({"values":values}).encode(), method="PUT",
        headers={"Authorization": f"Bearer {tok}", "Content-Type":"application/json"}))

def sheets_clear(tok, rng):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{urllib.parse.quote(rng)}:clear"
    urllib.request.urlopen(urllib.request.Request(url, data=b'{}',
        headers={"Authorization": f"Bearer {tok}", "Content-Type":"application/json"}))

def sheets_append(tok, rng, values):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{urllib.parse.quote(rng)}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
    urllib.request.urlopen(urllib.request.Request(url, data=json.dumps({"values":values}).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type":"application/json"}))

def ensure_archive_tab(tok):
    meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}?fields=sheets.properties.title"
    r = urllib.request.urlopen(urllib.request.Request(meta_url, headers={"Authorization": f"Bearer {tok}"}))
    titles = [s['properties']['title'] for s in json.loads(r.read())['sheets']]
    if ARCHIVE_TAB in titles: return
    body = {"requests":[{"addSheet":{"properties":{"title": ARCHIVE_TAB}}}]}
    urllib.request.urlopen(urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}:batchUpdate",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type":"application/json"}))
    sheets_put(tok, f"'{ARCHIVE_TAB}'!A1", [["할 일","상태","별점","카테고리","등록일","완료일","메모"]])

def send(text):
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode":"HTML"}).encode(),
        headers={'Content-Type': 'application/json'}))

def stars_count(s):
    return s.count("⭐") if s else 0

def run():
    tok = token()
    ensure_archive_tab(tok)
    rows = sheets_read(tok, f"'{SHEET_TAB}'!A1:G1000")
    if not rows: return
    header, body = rows[0], rows[1:]
    today = datetime.now().date()

    # 3일 이상 완료 → 아카이브 이동
    keep, archived = [], []
    for r in body:
        r = r + [""]*(7-len(r))
        if r[1] == "완료":
            reg = r[4] or today.isoformat()
            try: reg_d = datetime.strptime(reg, "%Y-%m-%d").date()
            except: reg_d = today
            if (today - reg_d).days >= 3:
                archived.append([r[0],r[1],r[2],r[3],r[4],today.isoformat(),r[6]])
                continue
        keep.append(r)
    if archived:
        sheets_append(tok, f"'{ARCHIVE_TAB}'!A1", archived)

    # 별점 내림차순 재정렬 (대기→진행→완료)
    order = {"회신대기":0, "대기":1, "진행":2, "완료":3}
    keep.sort(key=lambda r: (order.get(r[1], 3), -stars_count(r[2])))

    sheets_clear(tok, f"'{SHEET_TAB}'!A1:Z1000")
    sheets_put(tok, f"'{SHEET_TAB}'!A1", [header] + keep)
    apply_priority_colors(tok, keep)

    # 텔레그램 요약 (대기만) - 카드 스타일
    pending = [r for r in keep if r[1] == "대기"]
    m = f"📋 <b>오늘의 할일 ({today})</b>\n"
    m += f"━━━━━━━━━━━━━━\n\n"
    if not pending:
        m += "✅ 대기중인 할일 없음"
    else:
        for i, r in enumerate(pending, 1):
            n = stars_count(r[2])
            stars = "⭐" * n
            due = f"  ⏰{r[5]}" if r[5] else ""
            m += f"{stars}\n"
            m += f"<b>{i}. {r[0]}</b>{due}\n\n"
    m += f"━━━━━━━━━━━━━━\n"
    m += f"📊 대기 {len(pending)}건 · 아카이브 {len(archived)}건 이동"
    send(m)
    print(f"완료: 대기 {len(pending)}, 아카이브 {len(archived)}")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        import traceback
        err = f"⚠️ todo_daily.py 실패\n{type(e).__name__}: {e}\n\n{traceback.format_exc()[-500:]}"
        try: send(err)
        except: pass
        raise
