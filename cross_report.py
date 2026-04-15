"""
30분 슬롯 리포트 + 매 정시 GA↔카페24 교차검증 + 시트 누적 + 이상알림.
GitHub Actions 환경변수 기반. 로컬 ga_telegram_report.py(623줄)의 GHA 호환 버전.
"""
import warnings
warnings.filterwarnings("ignore")
import json, os, urllib.request, urllib.parse, base64
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric

# ===== 환경변수 =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GA_PROPERTY = os.environ["GA_PROPERTY"]
GA_CLIENT_ID = os.environ["GA_CLIENT_ID"]
GA_CLIENT_SECRET = os.environ["GA_CLIENT_SECRET"]
GA_REFRESH_TOKEN = os.environ["GA_REFRESH_TOKEN"]
CAFE24_CLIENT_ID = os.environ["CAFE24_CLIENT_ID"]
CAFE24_CLIENT_SECRET = os.environ["CAFE24_CLIENT_SECRET"]
CAFE24_REFRESH_TOKEN_INIT = os.environ["CAFE24_REFRESH_TOKEN"]
SHEET_ID = os.environ["SHEET_ID"]
CROSS_SHEET_ID = os.environ["CROSS_SHEET_ID"]

CAFE24_BASE = "https://goyonaband.cafe24api.com/api/v2"
CAFE24_ANALYTICS_BASE = "https://ca-api.cafe24data.com"
CAFE24_MALL_ID = "goyonaband"
PRODUCT_COST = int(os.environ.get("PRODUCT_COST", "0"))
PRODUCT_PRICE = int(os.environ.get("PRODUCT_PRICE", "89000"))
SHEET_RANGE = "A1"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cafe24_state.json")

# ===== 카페24 토큰 회전 =====
def load_saved_tokens():
    try:
        with open(TOKEN_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_tokens(access_token, refresh_token):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": access_token, "refresh_token": refresh_token,
                   "updated_at": datetime.utcnow().isoformat()}, f)

# ===== GA =====
def refresh_ga():
    data = urllib.parse.urlencode({
        "client_id": GA_CLIENT_ID, "client_secret": GA_CLIENT_SECRET,
        "refresh_token": GA_REFRESH_TOKEN, "grant_type": "refresh_token"
    }).encode()
    resp = urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data))
    token = json.loads(resp.read())['access_token']
    return BetaAnalyticsDataClient(credentials=Credentials(
        token=token, refresh_token=GA_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GA_CLIENT_ID, client_secret=GA_CLIENT_SECRET))

def ga_get(client, start, end):
    r = client.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions"),
                 Metric(name="userEngagementDuration"), Metric(name="engagementRate"),
                 Metric(name="averageSessionDuration")]
    ))
    if r.rows:
        v = r.rows[0].metric_values
        users = int(float(v[0].value))
        engage_total = float(v[2].value)
        per_user = (engage_total / users) if users > 0 else 0
        return {"users": users, "sessions": int(float(v[1].value)),
                "duration": per_user, "session_dur": float(v[4].value),
                "engage": float(v[3].value) * 100}
    return {"users": 0, "sessions": 0, "duration": 0, "session_dur": 0, "engage": 0}

# ===== 카페24 =====
def refresh_cafe24():
    saved = load_saved_tokens()
    refresh_token = saved.get("refresh_token", CAFE24_REFRESH_TOKEN_INIT)
    auth = base64.b64encode(f"{CAFE24_CLIENT_ID}:{CAFE24_CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": refresh_token
    }).encode()
    try:
        resp = urllib.request.urlopen(urllib.request.Request(
            "https://goyonaband.cafe24api.com/api/v2/oauth/token",
            data=data, headers={"Authorization": f"Basic {auth}",
                                "Content-Type": "application/x-www-form-urlencoded"}))
        new = json.loads(resp.read())
        save_tokens(new['access_token'], new['refresh_token'])
        return new['access_token']
    except Exception as e:
        print(f"카페24 토큰 갱신 실패: {e}")
        return saved.get("access_token", "")

def cafe24_orders(token, start, end):
    orders = []
    offset = 0
    while True:
        url = f"{CAFE24_BASE}/admin/orders?start_date={start}&end_date={end}&limit=100&offset={offset}"
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                "X-Cafe24-Api-Version": "2024-06-01"}))
            batch = json.loads(resp.read()).get('orders', [])
        except:
            break
        if not batch: break
        orders.extend(batch)
        if len(batch) < 100: break
        offset += 100
    revenue = sum(float(o.get('payment_amount') or 0) for o in orders)
    paid = sum(1 for o in orders if o.get('paid') == 'T')
    return len(orders), paid, revenue, orders

def cafe24_analytics(token, path, date_str, extra=""):
    if not token:
        return {}
    url = (f"{CAFE24_ANALYTICS_BASE}{path}?mall_id={CAFE24_MALL_ID}&shop_no=1"
           f"&start_date={date_str}&end_date={date_str}&{extra}")
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}"}), timeout=15)
        return json.loads(r.read())
    except:
        return {}

def cafe24_orders_in_slot(orders, slot_start_dt, slot_end_dt):
    s = slot_start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    e = slot_end_dt.strftime("%Y-%m-%dT%H:%M:%S")
    cnt = 0
    for o in orders:
        od = (o.get('order_date') or '')[:19]
        if o.get('paid') == 'T' and s <= od < e:
            cnt += 1
    return cnt

def judge_item(item, ga_v, c24_v):
    diff = ga_v - c24_v
    ab = abs(diff)
    if item == "구매건수":
        if ab <= 1:
            return ("주문완료 페이지 새로고침으로 GA purchase 이벤트 중복 발송 or 고객 1명 애드블록",
                    "정상 범위 내",
                    "1건 정도 차이는 쇼핑몰에서 흔히 발생. 무시 가능")
        elif ab == 2:
            return ("중복발송 누적 or 테스트결제 후 취소", "주의 범위",
                    "카페24 어드민에 취소된 주문 있는지 확인")
        else:
            return (f"{ab}건 차이 — 이벤트 무한루프 or purchase 이벤트 전체 고장", "비정상",
                    "GA head 스크립트 재시도 로직 과다발송 점검")
    elif item == "방문자":
        ratio = (ab / c24_v) if c24_v > 0 else 1
        if ab <= 10 or ratio <= 0.3:
            return ("GA(세션)와 카페24(방문수) 집계 기준 차이", "정상 범위 내",
                    "방문자 지표는 GA와 카페24가 원래 10~30% 차이 자연스러움")
        else:
            return ("GA 미설치 페이지 존재 or 봇/크롤러가 카페24에만 집계", "주의 범위",
                    "특정 페이지에서 GA 추적코드 누락되었는지 점검 필요")
    elif item == "매출":
        if ab == 0:
            return ("일치", "정상", "")
        units = ab / PRODUCT_PRICE if PRODUCT_PRICE else 0
        if units <= 1.2:
            return (f"구매건수 1건 차이에 따른 금액 차이 (객단가 ~{PRODUCT_PRICE:,}원)", "정상 범위 내",
                    "구매건수 항목과 연동된 차이")
        else:
            return (f"{units:.1f}건 분량 매출 불일치", "비정상",
                    "GA purchase 이벤트 value 파라미터 점검 필요")
    return ("", "", "")

# ===== 구글 시트 (GA OAuth 클라이언트 재사용) =====
def sheets_token():
    data = urllib.parse.urlencode({
        "client_id": GA_CLIENT_ID, "client_secret": GA_CLIENT_SECRET,
        "refresh_token": GA_REFRESH_TOKEN, "grant_type": "refresh_token"
    }).encode()
    resp = urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data))
    return json.loads(resp.read())['access_token']

def sheets_append(row):
    try:
        tok = sheets_token()
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{SHEET_RANGE}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        body = json.dumps({"values": [row]}).encode()
        urllib.request.urlopen(urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}))
    except Exception as e:
        print(f"시트 업로드 실패: {e}")

def cross_sheet_append(rows):
    if not rows:
        return
    try:
        tok = sheets_token()
        tab = urllib.parse.quote("확인사항")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{CROSS_SHEET_ID}/values/{tab}!A1:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        body = json.dumps({"values": rows}).encode()
        urllib.request.urlopen(urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}))
    except Exception as e:
        print(f"교차검증 시트 업로드 실패: {e}")

# ===== 텔레그램 =====
def send(text):
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=data, headers={'Content-Type': 'application/json'}))

def d(c, p):
    if p == 0: return "-"
    v = ((c - p) / p) * 100
    return f"+{v:.0f}%" if v > 0 else f"{v:.0f}%" if v < 0 else "0%"

# ===== 메인 =====
def run():
    ga = refresh_ga()
    c24 = refresh_cafe24()
    now = datetime.utcnow() + timedelta(hours=9)  # KST
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    week_str = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    t = ga_get(ga, "today", "today")
    y = ga_get(ga, "yesterday", "yesterday")

    r_hr = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date="today", end_date="today")],
        dimensions=[Dimension(name="hour")],
        metrics=[Metric(name="activeUsers")],
    ))

    # ===== 최근 30분(호출 시점 기준) GA Realtime API =====
    # 정시 슬롯이 아니라 "지금부터 30분 전까지" 활동한 사용자/이벤트
    from google.analytics.data_v1beta.types import RunRealtimeReportRequest
    try:
        r_rt_users = ga.run_realtime_report(RunRealtimeReportRequest(
            property=GA_PROPERTY, metrics=[Metric(name="activeUsers")]))
        realtime_users = int(float(r_rt_users.rows[0].metric_values[0].value)) if r_rt_users.rows else 0
    except Exception:
        realtime_users = 0

    # 최근 30분 이벤트별 카운트 (방문/조회/장바구니/결제시작/구매/회원가입)
    rt_event_counts = {}
    try:
        r_rt_ev = ga.run_realtime_report(RunRealtimeReportRequest(
            property=GA_PROPERTY,
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
        ))
        for row in r_rt_ev.rows or []:
            rt_event_counts[row.dimension_values[0].value] = int(float(row.metric_values[0].value))
    except Exception:
        pass

    slot_end_dt = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
    slot_start_dt = slot_end_dt - timedelta(minutes=30)
    slot_start_key = slot_start_dt.strftime("%Y%m%d%H%M")
    slot_end_key = slot_end_dt.strftime("%Y%m%d%H%M")

    rt_ev = {}
    r_slot_rows = []
    try:
        r_slot = ga.run_report(RunReportRequest(
            property=GA_PROPERTY,
            date_ranges=[DateRange(start_date="today", end_date="today")],
            dimensions=[Dimension(name="dateHourMinute"), Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
        ))
        r_slot_rows = list(r_slot.rows or [])
        for row in r_slot_rows:
            dhm = row.dimension_values[0].value
            name = row.dimension_values[1].value
            if slot_start_key <= dhm < slot_end_key:
                rt_ev[name] = rt_ev.get(name, 0) + int(float(row.metric_values[0].value))
    except Exception:
        pass

    # slot_visitors는 정시 교차검증에서만 사용됨

    t_o, t_p, t_r, t_orders_raw = cafe24_orders(c24, today_str, today_str)
    y_o, y_p, y_r, _ = cafe24_orders(c24, yesterday_str, yesterday_str)

    slot_purchase_cafe24 = cafe24_orders_in_slot(t_orders_raw, slot_start_dt, slot_end_dt)

    # ===== 정시 교차검증 =====
    cross_check_block = ""
    cross_alert_block = ""
    if slot_end_dt.minute == 0:
        hour_start = slot_end_dt - timedelta(hours=1)
        hour_end = slot_end_dt
        hs = hour_start.strftime("%Y%m%d%H%M")
        he = hour_end.strftime("%Y%m%d%H%M")
        target_hour = hour_start.hour
        date_key = hour_start.strftime("%Y-%m-%d")
        hour_label = f"{hour_start.strftime('%H:%M')}~{hour_end.strftime('%H:%M')}"

        ga_purchase = ga_view = ga_session_start = ga_page_view = 0
        for row in r_slot_rows:
            dhm = row.dimension_values[0].value
            name = row.dimension_values[1].value
            if hs <= dhm < he:
                cnt = int(float(row.metric_values[0].value))
                if name == 'purchase': ga_purchase += cnt
                elif name == 'view_item': ga_view += cnt
                elif name == 'session_start': ga_session_start += cnt
                elif name == 'page_view': ga_page_view += cnt

        c24_purchase = 0
        c24_revenue = 0.0
        s_iso = hour_start.strftime("%Y-%m-%dT%H:%M:%S")
        e_iso = hour_end.strftime("%Y-%m-%dT%H:%M:%S")
        for o in t_orders_raw:
            od = (o.get('order_date') or '')[:19]
            if o.get('paid') == 'T' and s_iso <= od < e_iso:
                c24_purchase += 1
                c24_revenue += float(o.get('payment_amount') or 0)

        an_visit = cafe24_analytics(c24, "/visitors/view", date_key, "format_type=hour")
        c24_visit = 0
        for row in (an_visit.get('view') or []):
            if row.get('hour') == target_hour:
                c24_visit = row.get('visit_count', 0)
                break

        ga_revenue = 0.0
        try:
            r_rev = ga.run_report(RunReportRequest(
                property=GA_PROPERTY,
                date_ranges=[DateRange(start_date="today", end_date="today")],
                dimensions=[Dimension(name="dateHourMinute"), Dimension(name="eventName")],
                metrics=[Metric(name="eventValue")],
            ))
            for row in r_rev.rows or []:
                dhm = row.dimension_values[0].value
                name = row.dimension_values[1].value
                if hs <= dhm < he and name == 'purchase':
                    ga_revenue += float(row.metric_values[0].value)
        except Exception:
            pass

        anomalies = []
        items = [
            ("구매건수", ga_purchase, c24_purchase, 1,
             "GA 'purchase' 이벤트 수 vs 카페24 결제완료 주문 수"),
            ("방문자", ga_session_start, c24_visit, 5,
             "GA 세션 시작 수 vs 카페24 집계 방문 수"),
            ("매출", int(ga_revenue), int(c24_revenue), 10000,
             "GA purchase 이벤트 금액 vs 카페24 실결제 금액"),
        ]
        for name, ga_v, c24_v, threshold, desc in items:
            diff = ga_v - c24_v
            if abs(diff) >= threshold:
                anomalies.append({"date": date_key, "slot": hour_label, "item": name,
                                  "ga": ga_v, "c24": c24_v, "diff": diff, "desc": desc})

        status_map = {True: "⚠️ 차이", False: "✅ 일치"}
        cross_check_block = f"\n<b>[ 교차검증 {hour_label} ]</b>\n\n"
        for name, ga_v, c24_v, threshold, _ in items:
            diff = ga_v - c24_v
            flag = abs(diff) >= threshold
            fmt = f"{ga_v:,} / {c24_v:,}" if name == "매출" else f"{ga_v} / {c24_v}"
            sign = f"{'+' if diff>=0 else ''}{diff:,}"
            cross_check_block += f"  {name:<5} GA/카24 <b>{fmt}</b>  ({sign})  {status_map[flag]}\n"

        if anomalies:
            now_str = now.strftime("%Y-%m-%d %H:%M")
            def one_liner(a):
                suffix = "원" if a['item'] == '매출' else ("건" if a['item'] == '구매건수' else "명")
                amount = f"{abs(a['diff']):,}{suffix}"
                direction = "더 많음" if a['diff'] > 0 else "더 적음"
                return f"{a['item']}: GA가 {amount} {direction}"
            def make_row(a):
                cause, normal, note = judge_item(a["item"], a["ga"], a["c24"])
                return [now_str, a["date"], a["slot"], a["item"], one_liner(a),
                        a["desc"], a["ga"], a["c24"], a["diff"], cause, normal, note, ""]
            cross_sheet_append([make_row(a) for a in anomalies])

            alert = f"🔔 <b>교차검증 이상 감지 ({hour_label})</b>\nGA와 카페24 숫자 불일치 항목 아래.\n\n"
            for a in anomalies:
                ga_v = f"{a['ga']:,}원" if a['item'] == '매출' else f"{a['ga']}"
                c24_v = f"{a['c24']:,}원" if a['item'] == '매출' else f"{a['c24']}"
                sign = f"{'+' if a['diff']>=0 else ''}{a['diff']:,}"
                which = "GA가 " + ("많음" if a['diff'] > 0 else "적음")
                alert += (f"━━━━━━━━━━━━━━\n<b>■ {a['item']}</b>  ({which} · 차이 {sign})\n"
                          f"  GA: {ga_v}\n  카페24: {c24_v}\n  ↳ {a['desc']}\n")
            alert += "━━━━━━━━━━━━━━\n시트 '확인사항' 탭에 기록됨."
            cross_alert_block = alert

    # 계산
    t_cost = t_o * PRODUCT_COST
    t_profit = t_r - t_cost
    t_cvr = (t_o / t['users'] * 100) if t['users'] > 0 else 0
    y_cvr = (y_o / y['users'] * 100) if y['users'] > 0 else 0
    t_profit_rate = (t_profit / t_r * 100) if t_r > 0 else 0
    t_aov = t_r / t_o if t_o > 0 else 0

    slot_label = f"{slot_start_dt.strftime('%m.%d %H:%M')} ~ {slot_end_dt.strftime('%m.%d %H:%M')}"
    # 최근 30분(호출 시점 기준) 라벨
    rt_label = f"{(now - timedelta(minutes=30)).strftime('%H:%M')} ~ {now.strftime('%H:%M')}"
    # 최근 30분 이벤트 (Realtime API 기준 — 동일 사용자들의 행동)
    rt_visit = rt_event_counts.get('session_start', 0)
    rt_view = rt_event_counts.get('view_item', 0)
    rt_cart = rt_event_counts.get('add_to_cart', 0)
    rt_checkout = rt_event_counts.get('begin_checkout', 0)
    rt_purchase = rt_event_counts.get('purchase', 0)
    rt_signup = rt_event_counts.get('sign_up', 0)

    m = "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥\n"
    m += f"<b>goyona admin</b>\n<b>{slot_label}</b>\n\n"
    m += "<b>[ 매출 ]</b>\n\n"
    m += f"  매출         <b>{t_r:,.0f}</b>원  {d(t_r, y_r)}\n"
    m += f"  주문         <b>{t_o}</b>건  {d(t_o, y_o)}\n"
    m += f"  결제완료     <b>{t_p}</b>건\n"
    if t_o > 0:
        m += f"  객단가       <b>{t_aov:,.0f}</b>원\n"
    m += "\n<b>[ 비용/수익 ]</b>\n\n"
    m += f"  원가         <b>{t_cost:,.0f}</b>원\n"
    m += f"  광고비       <b>미연결</b>\n"
    m += f"  순이익       <b>{t_profit:,.0f}</b>원\n"
    if t_r > 0:
        m += f"  순이익률     <b>{t_profit_rate:.1f}%</b>\n"
    m += "\n<b>[ 전환 ]</b>\n\n"
    m += f"  전환율       <b>{t_cvr:.2f}%</b>  (어제 {y_cvr:.2f}%)\n\n"

    m += "<b>[ 트래픽 ]</b>\n\n"
    m += f"  오늘 누적 방문자  <b>{t['users']:,}</b>명  {d(t['users'], y['users'])}\n"
    m += f"  1인당 평균 체류  <b>{t['duration']:.0f}초</b> ({t['duration']/60:.1f}분)\n\n"

    # 최근 30분 = 호출 시점 기준 정확히 30분 윈도우 (GA Realtime API)
    m += f"<b>[ 최근 30분 활동 ({rt_label}) ]</b>\n\n"
    m += f"  활성 사용자  <b>{realtime_users}</b>명\n"
    m += f"  방문         <b>{rt_visit}</b>회\n"
    m += f"  상품조회     <b>{rt_view}</b>회\n"
    m += f"  장바구니     <b>{rt_cart}</b>회\n"
    m += f"  결제시작     <b>{rt_checkout}</b>회\n"
    m += f"  구매완료     <b>{rt_purchase}</b>건\n"
    m += f"  회원가입     <b>{rt_signup}</b>명\n"

    m += cross_check_block
    send(m)
    if cross_alert_block:
        send(cross_alert_block)

    sheets_append([
        now.strftime("%Y-%m-%d %H:%M"), rt_label,
        t_r, t_o, t_p, t_aov, t_cost, t_profit, round(t_profit_rate, 1),
        round(t_cvr, 2), t['users'], rt_visit, round(t['duration'], 0),
        rt_view, rt_cart, rt_checkout, rt_purchase, rt_signup,
    ])
    print("전송 완료!")

if __name__ == "__main__":
    run()
