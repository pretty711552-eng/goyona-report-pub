import warnings
warnings.filterwarnings("ignore")
import json, urllib.request, urllib.parse, base64, os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric

# ===== 설정 =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GA_PROPERTY = os.environ["GA_PROPERTY"]
GA_CLIENT_ID = os.environ["GA_CLIENT_ID"]
GA_CLIENT_SECRET = os.environ["GA_CLIENT_SECRET"]
GA_REFRESH_TOKEN = os.environ["GA_REFRESH_TOKEN"]
CAFE24_CLIENT_ID = os.environ["CAFE24_CLIENT_ID"]
CAFE24_CLIENT_SECRET = os.environ["CAFE24_CLIENT_SECRET"]
CAFE24_REFRESH_TOKEN = os.environ["CAFE24_REFRESH_TOKEN"]
CAFE24_BASE = "https://goyonaband.cafe24api.com/api/v2"
PRODUCT_COST = int(os.environ.get("PRODUCT_COST", "0"))
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cafe24_state.json")

# ===== 카페24 토큰 관리 =====
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

# ===== 카페24 =====
def refresh_cafe24():
    auth = base64.b64encode(f"{CAFE24_CLIENT_ID}:{CAFE24_CLIENT_SECRET}".encode()).decode()
    saved = load_saved_tokens()
    refresh_token = saved.get("refresh_token", CAFE24_REFRESH_TOKEN)

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": refresh_token
    }).encode()
    try:
        resp = urllib.request.urlopen(urllib.request.Request(
            "https://goyonaband.cafe24api.com/api/v2/oauth/token",
            data=data, headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}))
        result = json.loads(resp.read())
        save_tokens(result["access_token"], result["refresh_token"])
        return result["access_token"]
    except:
        pass

    if refresh_token != CAFE24_REFRESH_TOKEN:
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token", "refresh_token": CAFE24_REFRESH_TOKEN
        }).encode()
        try:
            resp = urllib.request.urlopen(urllib.request.Request(
                "https://goyonaband.cafe24api.com/api/v2/oauth/token",
                data=data, headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}))
            result = json.loads(resp.read())
            save_tokens(result["access_token"], result["refresh_token"])
            return result["access_token"]
        except:
            pass

    if saved.get("access_token"):
        return saved["access_token"]
    return ""

def cafe24_orders(token, start, end):
    if not token:
        return [], 0, 0, 0
    orders = []
    offset = 0
    while True:
        url = f"{CAFE24_BASE}/admin/orders?start_date={start}&end_date={end}&limit=100&offset={offset}"
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                "X-Cafe24-Api-Version": "2026-03-01"}))
            batch = json.loads(resp.read()).get('orders', [])
        except:
            break
        if not batch: break
        orders.extend(batch)
        if len(batch) < 100: break
        offset += 100
    # 결제완료(카드/네이버페이) + 무통장 입금확인만 매출로 집계
    paid_orders = [o for o in orders if o.get('paid') == 'T']
    revenue = sum(float(o.get('payment_amount') or 0) for o in paid_orders)
    return orders, len(orders), len(paid_orders), revenue

# ===== 텔레그램 =====
def send(text):
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=data, headers={'Content-Type': 'application/json'}))

# ===== 메인 =====
def run():
    ga = refresh_ga()
    c24 = refresh_cafe24()
    now = datetime.utcnow() + timedelta(hours=9)
    today_str = now.strftime("%Y-%m-%d")
    hour_ago = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")

    # GA 오늘 누적
    r = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date="today", end_date="today")],
        metrics=[Metric(name="activeUsers"), Metric(name="userEngagementDuration"), Metric(name="sessions"), Metric(name="engagementRate")]
    ))
    t_users = int(float(r.rows[0].metric_values[0].value)) if r.rows else 0
    t_engage_total = float(r.rows[0].metric_values[1].value) if r.rows else 0
    t_sessions = int(float(r.rows[0].metric_values[2].value)) if r.rows else 0
    t_engage = float(r.rows[0].metric_values[3].value) * 100 if r.rows else 0
    t_dur = (t_engage_total / t_users) if t_users > 0 else 0

    # 시간대별 방문자
    r_hr = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date="today", end_date="today")],
        dimensions=[Dimension(name="hour")],
        metrics=[Metric(name="activeUsers")],
    ))
    hour_users = 0
    if r_hr.rows:
        for row in r_hr.rows:
            if row.dimension_values[0].value.zfill(2) == str(now.hour).zfill(2):
                hour_users = int(float(row.metric_values[0].value))

    # GA 이벤트 (퍼널)
    r_events = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date="today", end_date="today")],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
    ))
    ev = {}
    if r_events.rows:
        for row in r_events.rows:
            ev[row.dimension_values[0].value] = int(float(row.metric_values[0].value))

    # 채널별
    r_ch = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date="today", end_date="today")],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="activeUsers"), Metric(name="engagementRate")],
    ))

    # 카페24 주문
    today_orders, t_o, t_p, t_r = cafe24_orders(c24, today_str, today_str)
    # 최근 1시간 주문 (결제완료만)
    hour_orders = [o for o in today_orders if o.get('order_date', '') >= hour_ago and o.get('paid') == 'T']
    h_count = len(hour_orders)
    h_revenue = sum(float(o.get('payment_amount') or 0) for o in hour_orders)

    t_cost = t_p * PRODUCT_COST
    t_profit = t_r - t_cost
    t_cvr = (t_p / t_users * 100) if t_users > 0 else 0
    t_aov = t_r / t_p if t_p > 0 else 0

    # 퍼널
    f_visit = t_users
    f_signup = ev.get('first_visit', 0)
    f_view_item = ev.get('view_item', 0)
    f_add_cart = ev.get('add_to_cart', 0)
    f_checkout = ev.get('begin_checkout', 0)
    f_purchase = t_p

    # 메시지
    m = ""
    m += "━━━━━━━━━━━━━━━━━━━━━━\n"
    m += f"  <b>고요나 리포트</b>\n"
    m += f"  {now.strftime('%Y.%m.%d %H:%M')}\n"
    m += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    m += "<b>[ 매출 ]</b>\n\n"
    m += f"  오늘 누적     <b>{t_r:,.0f}</b>원  ({t_users:,}명 방문)\n"
    m += f"  최근 1시간    <b>+{h_revenue:,.0f}</b>원  ({h_count}건)\n"
    m += f"  주문 {t_o}건 / 결제완료 {t_p}건\n"
    if t_o > 0:
        m += f"  객단가        <b>{t_aov:,.0f}</b>원\n"
    m += "\n"

    m += "<b>[ 전환 퍼널 ]</b>\n\n"
    m += f"  방문자       <b>{f_visit}</b>명\n"
    m += f"  신규방문     <b>{f_signup}</b>명\n"
    m += f"  상품조회     <b>{f_view_item}</b>회\n"
    m += f"  장바구니     <b>{f_add_cart}</b>회\n"
    m += f"  결제시작     <b>{f_checkout}</b>회\n"
    m += f"  구매완료     <b>{f_purchase}</b>건\n"
    m += "\n"

    m += "<b>[ 방문자 ]</b>\n\n"
    m += f"  오늘 누적     <b>{t_users:,}</b>명\n"
    m += f"  {now.hour}시 방문자   <b>{hour_users}</b>명\n"
    m += f"  체류시간      <b>{t_dur:.0f}초</b> ({t_dur/60:.1f}분)\n\n"

    m += "<b>[ 수익 ]</b>\n\n"
    m += f"  원가          <b>{t_cost:,.0f}</b>원\n"
    m += f"  광고비        <b>미연결</b>\n"
    m += f"  순이익        <b>{t_profit:,.0f}</b>원  (광고비 제외)\n"
    m += f"  전환율        <b>{t_cvr:.2f}%</b>\n\n"

    ch_map = {"Paid Social":"유료광고", "Direct":"직접", "Organic Search":"검색",
              "Organic Social":"소셜", "Referral":"추천", "Cross-network":"크로스",
              "Paid Other":"기타광고", "Paid Search":"검색광고", "Organic Video":"영상",
              "Unassigned":"미분류"}
    m += "<b>[ 채널별 ]</b>\n\n"
    if r_ch.rows:
        for row in sorted(r_ch.rows, key=lambda x: int(float(x.metric_values[0].value)), reverse=True):
            ch = ch_map.get(row.dimension_values[0].value, row.dimension_values[0].value[:8])
            u = int(float(row.metric_values[0].value))
            e = float(row.metric_values[1].value) * 100
            m += f"  {ch:<8} {u:>4}명  참여 {e:.0f}%\n"

    m += "\n━━━━━━━━━━━━━━━━━━━━━━"

    send(m)
    print("전송 완료!")

if __name__ == "__main__":
    run()
