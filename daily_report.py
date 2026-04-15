import warnings
warnings.filterwarnings("ignore")
import json, urllib.request, urllib.parse, base64, os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric

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
CAFE24_ANALYTICS_BASE = "https://ca-api.cafe24data.com"
CAFE24_MALL_ID = "goyonaband"
PRODUCT_COST = int(os.environ.get("PRODUCT_COST", "0"))
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "")
USD_KRW = float(os.environ.get("USD_KRW", "1380"))
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cafe24_state.json")


def meta_daily_spend(date_str):
    """메타 광고 특정일 합계. 토큰 없거나 오류면 None 반환."""
    if not META_ACCESS_TOKEN or not META_AD_ACCOUNT_ID:
        return None
    try:
        params = {
            "access_token": META_ACCESS_TOKEN,
            "fields": "spend,impressions,clicks,actions,action_values",
            "level": "account",
            "time_range": json.dumps({"since": date_str, "until": date_str}),
        }
        url = f"https://graph.facebook.com/v21.0/{META_AD_ACCOUNT_ID}/insights?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        rows = data.get("data", [])
        if not rows:
            return {"spend": 0, "impressions": 0, "clicks": 0, "purchases": 0, "purchase_value": 0}
        row = rows[0]
        spend_krw = int(float(row.get("spend", 0)) * USD_KRW)
        purchase_keys = ("purchase", "offsite_conversion.fb_pixel_purchase", "omni_purchase")
        purchases = sum(int(a["value"]) for a in row.get("actions", []) if a["action_type"] in purchase_keys)
        purchase_val = sum(float(a["value"]) for a in row.get("action_values", []) if a["action_type"] in purchase_keys)
        return {
            "spend": spend_krw,
            "impressions": int(row.get("impressions", 0)),
            "clicks": int(row.get("clicks", 0)),
            "purchases": purchases,
            "purchase_value": int(purchase_val * USD_KRW),
        }
    except Exception as e:
        print(f"메타 광고 조회 실패: {e}")
        return None

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

def refresh_cafe24():
    # 로컬: cafe24_refresh.py가 ~/cafe24_token.json을 매시간 유지 → 우선 사용
    local_token = os.path.expanduser("~/cafe24_token.json")
    if os.path.exists(local_token):
        try:
            with open(local_token) as f:
                return json.load(f)["access_token"]
        except:
            pass
    # GitHub Actions fallback: 자체 refresh
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
    paid_orders = [o for o in orders if o.get('paid') == 'T']
    def order_revenue(o):
        # 네이버페이 선불금 등은 payment_amount=0으로 찍히므로 상품구매금액(order_price_amount) 우선
        actual = o.get('actual_order_amount') or {}
        price = float(actual.get('order_price_amount') or 0)
        if price > 0:
            return price
        return float(o.get('payment_amount') or 0)
    revenue = sum(order_revenue(o) for o in paid_orders)
    # 회원 vs 비회원
    member_cnt = sum(1 for o in paid_orders if o.get('member_id'))
    guest_cnt = len(paid_orders) - member_cnt
    return orders, len(orders), len(paid_orders), revenue, member_cnt, guest_cnt, paid_orders

def cafe24_analytics(token, path, date_str, extra=""):
    """카페24 애널리틱스 API 호출. 실패 시 빈 dict."""
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

def clean_name(s):
    """상품명 HTML 태그/&nbsp; 정리."""
    import re
    s = re.sub(r'<[^>]+>', '', s or '')
    s = s.replace('&nbsp;', ' ').strip()
    return s[:22]

def send(text):
    data = json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=data, headers={'Content-Type': 'application/json'}))

def ga_daily(ga, date_str):
    r = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        metrics=[Metric(name="activeUsers"), Metric(name="userEngagementDuration"),
                 Metric(name="sessions"), Metric(name="engagementRate")]
    ))
    users = int(float(r.rows[0].metric_values[0].value)) if r.rows else 0
    engage_total = float(r.rows[0].metric_values[1].value) if r.rows else 0
    sessions = int(float(r.rows[0].metric_values[2].value)) if r.rows else 0
    engage = float(r.rows[0].metric_values[3].value) * 100 if r.rows else 0
    dur = (engage_total / users) if users > 0 else 0
    r_ev = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
    ))
    ev = {}
    if r_ev.rows:
        for row in r_ev.rows:
            ev[row.dimension_values[0].value] = int(float(row.metric_values[0].value))
    # 신규 vs 재방문
    r_nr = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        dimensions=[Dimension(name="newVsReturning")],
        metrics=[Metric(name="activeUsers")],
    ))
    new_users = 0
    ret_users = 0
    if r_nr.rows:
        for row in r_nr.rows:
            v = row.dimension_values[0].value
            cnt = int(float(row.metric_values[0].value))
            if v == "new":
                new_users = cnt
            elif v == "returning":
                ret_users = cnt
    return {"users": users, "sessions": sessions, "engage": engage, "dur": dur, "ev": ev,
            "new_users": new_users, "ret_users": ret_users}

def pct(cur, prev):
    if prev == 0:
        return " (신규)" if cur > 0 else ""
    delta = (cur - prev) / prev * 100
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "―")
    return f" ({arrow}{abs(delta):.1f}%)"

def run():
    ga = refresh_ga()
    c24 = refresh_cafe24()
    now = datetime.utcnow() + timedelta(hours=9)
    yday = now - timedelta(days=1)
    dday = now - timedelta(days=2)
    y_str = yday.strftime("%Y-%m-%d")
    d_str = dday.strftime("%Y-%m-%d")
    dow = ["월","화","수","목","금","토","일"][yday.weekday()]

    y = ga_daily(ga, y_str)
    d = ga_daily(ga, d_str)

    r_ch = ga.run_report(RunReportRequest(
        property=GA_PROPERTY,
        date_ranges=[DateRange(start_date=y_str, end_date=y_str)],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="activeUsers"), Metric(name="engagementRate")],
    ))

    _, _, y_p, y_rev, y_mem, y_guest, y_paid = cafe24_orders(c24, y_str, y_str)
    _, _, d_p, d_rev, d_mem, d_guest, d_paid = cafe24_orders(c24, d_str, d_str)
    # 회원 주문 기준 첫구매/재구매 (비회원은 판단불가)
    y_first = sum(1 for o in y_paid if o.get('first_order') == 'T')
    y_repeat = sum(1 for o in y_paid if o.get('member_id') and o.get('first_order') != 'T')
    d_first = sum(1 for o in d_paid if o.get('first_order') == 'T')
    d_repeat = sum(1 for o in d_paid if o.get('member_id') and o.get('first_order') != 'T')

    cost = y_p * PRODUCT_COST
    cvr = (y_p / y["users"] * 100) if y["users"] > 0 else 0
    d_cvr = (d_p / d["users"] * 100) if d["users"] > 0 else 0
    aov = y_rev / y_p if y_p > 0 else 0
    d_aov = d_rev / d_p if d_p > 0 else 0
    d_cost = d_p * PRODUCT_COST

    # 메타 광고비/ROAS 연결
    y_meta = meta_daily_spend(y_str) or {}
    d_meta = meta_daily_spend(d_str) or {}
    y_ad = y_meta.get("spend", 0)
    d_ad = d_meta.get("spend", 0)
    profit = y_rev - cost - y_ad
    d_profit = d_rev - d_cost - d_ad
    roas = (y_rev / y_ad * 100) if y_ad > 0 else 0
    d_roas = (d_rev / d_ad * 100) if d_ad > 0 else 0

    m = ""
    m += "━━━━━━━━━━━━━━━━━━━━━━\n"
    m += f"  <b>고요나 전날 매출 정리</b>\n"
    m += f"  {yday.strftime('%Y.%m.%d')} ({dow})\n"
    m += f"  * 괄호는 전일 대비\n"
    m += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    m += "<b>[ 매출 ]</b>\n\n"
    m += f"  총 매출       <b>{y_rev:,.0f}</b>원{pct(y_rev, d_rev)}\n"
    m += f"  결제완료      <b>{y_p}</b>건{pct(y_p, d_p)}\n"
    if y_p > 0:
        m += f"  객단가        <b>{aov:,.0f}</b>원{pct(aov, d_aov)}\n"
    m += "\n"

    m += "<b>[ 수익 ]</b>\n\n"
    m += f"  원가          <b>{cost:,.0f}</b>원{pct(cost, d_cost)}\n"
    if y_ad > 0 or d_ad > 0:
        m += f"  광고비(메타)  <b>{y_ad:,.0f}</b>원{pct(y_ad, d_ad)}\n"
        m += f"  순이익        <b>{profit:,.0f}</b>원{pct(profit, d_profit)}\n"
        m += f"  ROAS          <b>{roas:,.0f}%</b>{pct(roas, d_roas)}\n"
    else:
        m += f"  광고비        <b>미연결</b>  (메타 토큰 만료 또는 미설정)\n"
        m += f"  순이익        <b>{profit:,.0f}</b>원{pct(profit, d_profit)}  (광고비 제외)\n"
    m += f"  전환율        <b>{cvr:.2f}%</b>{pct(cvr, d_cvr)}\n\n"

    m += "<b>[ 방문 ]</b>\n\n"
    m += f"  방문자        <b>{y['users']:,}</b>명{pct(y['users'], d['users'])}\n"
    m += f"  세션          <b>{y['sessions']:,}</b>회{pct(y['sessions'], d['sessions'])}\n"
    m += f"  체류시간      <b>{y['dur']:.0f}초</b> ({y['dur']/60:.1f}분){pct(y['dur'], d['dur'])}\n"
    m += f"  구매전환율    <b>{cvr:.2f}%</b>{pct(cvr, d_cvr)}\n\n"

    f_visit = y['users']
    f_view = y['ev'].get('view_item', 0)
    f_cart = y['ev'].get('add_to_cart', 0)
    f_checkout = y['ev'].get('begin_checkout', 0)
    f_purchase = y_p
    def rate(cur, base):
        return f" → {cur/base*100:.1f}%" if base > 0 else ""
    m += "<b>[ 전환 퍼널 ]</b>\n\n"
    m += f"  방문자       <b>{f_visit}</b>명{pct(f_visit, d['users'])}\n"
    m += f"  상품조회     <b>{f_view}</b>회{rate(f_view, f_visit)}\n"
    m += f"  장바구니     <b>{f_cart}</b>회{rate(f_cart, f_view)}\n"
    m += f"  결제시작     <b>{f_checkout}</b>회{rate(f_checkout, f_view)}\n"
    m += f"  구매완료     <b>{f_purchase}</b>건{rate(f_purchase, f_checkout)}\n"
    m += f"  (조회→구매 {f_purchase/f_view*100:.1f}%)\n\n" if f_view > 0 else "\n"

    m += "<b>[ 고객 구성 ]</b>\n\n"
    tot_visit = y['new_users'] + y['ret_users']
    new_pct = y['new_users']/tot_visit*100 if tot_visit>0 else 0
    ret_pct = y['ret_users']/tot_visit*100 if tot_visit>0 else 0
    d_tot = d['new_users'] + d['ret_users']
    d_new_pct = d['new_users']/d_tot*100 if d_tot>0 else 0
    d_ret_pct = d['ret_users']/d_tot*100 if d_tot>0 else 0
    m += f"  신규방문      <b>{y['new_users']:,}</b>명 ({new_pct:.0f}%){pct(y['new_users'], d['new_users'])}\n"
    m += f"  재방문        <b>{y['ret_users']:,}</b>명 ({ret_pct:.0f}%){pct(y['ret_users'], d['ret_users'])}\n"
    m += f"  회원 주문     <b>{y_mem}</b>건{pct(y_mem, d_mem)}\n"
    m += f"  비회원 주문   <b>{y_guest}</b>건{pct(y_guest, d_guest)}\n"
    m += f"  첫 구매       <b>{y_first}</b>건{pct(y_first, d_first)}\n"
    m += f"  재구매        <b>{y_repeat}</b>건{pct(y_repeat, d_repeat)}\n"
    m += f"  (비회원은 재구매 판단불가)\n\n"

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

    # ===== 카페24 애널리틱스 (원천 데이터) =====
    an_visitors = cafe24_analytics(c24, "/visitors/view", y_str, "format_type=day")
    an_carts = cafe24_analytics(c24, "/carts/action", y_str, "limit=5")
    an_keywords = cafe24_analytics(c24, "/visitpaths/keywords", y_str, "limit=10")
    an_members = cafe24_analytics(c24, "/members/sales", y_str)
    an_prod_view = cafe24_analytics(c24, "/products/view", y_str, "limit=5")
    an_prod_sales = cafe24_analytics(c24, "/products/sales", y_str, "limit=5")

    m += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    m += "<b>[ 카페24 원천 데이터 ]</b>\n\n"

    # 방문자 (카페24 집계 기준)
    vis = (an_visitors.get('view') or [{}])[0]
    if vis:
        m += f"  방문 (카페24)  <b>{vis.get('visit_count',0):,}</b>회"
        m += f"  (신규 {vis.get('first_visit_count',0)} / 재방문 {vis.get('re_visit_count',0)})\n\n"

    # 회원/비회원 매출 비중
    ms = (an_members.get('sales') or [{}])[0]
    if ms:
        m_cnt = ms.get('member_order_count', 0)
        m_amt = float(ms.get('member_order_amount') or 0)
        g_cnt = ms.get('nonmember_order_count', 0)
        g_amt = float(ms.get('nonmember_order_amount') or 0)
        tot_amt = m_amt + g_amt
        if tot_amt > 0:
            m += "<b>[ 회원 vs 비회원 매출 ]</b>\n\n"
            m += f"  회원    <b>{m_cnt}</b>건  <b>{m_amt:,.0f}</b>원 ({m_amt/tot_amt*100:.0f}%)\n"
            m += f"  비회원  <b>{g_cnt}</b>건  <b>{g_amt:,.0f}</b>원 ({g_amt/tot_amt*100:.0f}%)\n\n"

    # 장바구니 담기율 Top
    carts = an_carts.get('action') or []
    if carts:
        m += "<b>[ 장바구니 담기율 Top ]</b>\n\n"
        for c in carts[:5]:
            nm = clean_name(c.get('product_name',''))
            m += f"  {nm}\n    조회 {c.get('count',0)} → 담기 {c.get('add_cart_count',0)} ({c.get('add_cart_rate','0')}%)\n"
        m += "\n"

    # 상품별 매출 Top
    ps = an_prod_sales.get('sales') or []
    if ps:
        m += "<b>[ 상품별 매출 Top ]</b>\n\n"
        for p in ps[:5]:
            nm = clean_name(p.get('product_name',''))
            amt = float(p.get('order_amount') or p.get('sales_amount') or 0)
            cnt = p.get('order_count') or p.get('sales_count') or 0
            m += f"  {nm}  <b>{amt:,.0f}</b>원 ({cnt}건)\n"
        m += "\n"

    # 유입 키워드 Top
    kws = an_keywords.get('keywords') or []
    if kws:
        m += "<b>[ 유입 키워드 Top 10 ]</b>\n\n"
        for k in kws[:10]:
            kw = (k.get('keyword') or '').strip()[:20]
            m += f"  {kw}  <b>{k.get('visit_count',0)}</b>회\n"
        m += "\n"

    m += "━━━━━━━━━━━━━━━━━━━━━━"

    send(m)
    print("전날 리포트 전송 완료!")

if __name__ == "__main__":
    run()
