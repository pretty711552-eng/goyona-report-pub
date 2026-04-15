"""투두 빠른 추가 + 즉시 텔레그램 발송.
사용: python3 todo_add.py "할 일" [별점수=3] [카테고리=개인] [마감일=] [메모=]
- ⭐⭐⭐⭐⭐ (별점5)는 최상단으로 이동 + 빨강+볼드 적용
- 추가 후 텔레그램으로 즉시 알림
"""
import sys, json, urllib.request, urllib.parse
from datetime import datetime
sys.path.insert(0, '/Users/sanghun/goyona-report')
from todo_daily import (token, sheets_read, sheets_put, sheets_clear,
                        sheets_append, apply_priority_colors, send,
                        SHEET_TAB, SHEET_ID, stars_count)

def add(title, stars=3, category="개인", due="", memo=""):
    tok = token()
    today = datetime.now().strftime('%Y-%m-%d')
    star_str = "⭐" * int(stars)
    new_row = [title, "대기", star_str, category, today, due, memo]

    rows = sheets_read(tok, f"'{SHEET_TAB}'!A1:G1000")
    header = rows[0] if rows else ["할 일","상태","별점","카테고리","등록일","마감일","메모"]
    body = rows[1:] if rows else []

    # 별점5면 최상단, 아니면 말단
    if int(stars) == 5:
        body = [new_row] + body
    else:
        # 대기 블록 안에서 별점 내림차순 정렬 유지
        body.append(new_row)
        order = {"회신대기":0, "대기":1, "진행":2, "완료":3}
        body.sort(key=lambda r: (order.get((r+[""]*7)[1], 3), -stars_count((r+[""]*7)[2])))

    sheets_clear(tok, f"'{SHEET_TAB}'!A1:Z1000")
    sheets_put(tok, f"'{SHEET_TAB}'!A1", [header] + body)
    apply_priority_colors(tok, body)

    # 텔레그램 즉시 발송
    urgency = "🚨 <b>최우선</b>\n" if int(stars) == 5 else ""
    msg = (f"{urgency}📌 <b>투두 추가</b>\n"
           f"━━━━━━━━━━━━━━\n"
           f"{star_str}\n"
           f"<b>{title}</b>\n"
           f"카테고리: {category}" + (f" · 마감 ⏰{due}" if due else "") + "\n"
           f"등록일: {today}")
    send(msg)
    print(f"추가+알림 완료: {title} ({star_str})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: python3 todo_add.py '할 일' [별점=3] [카테고리=개인] [마감일] [메모]")
        sys.exit(1)
    args = sys.argv[1:] + [""] * 5
    add(args[0], args[1] or 3, args[2] or "개인", args[3], args[4])
