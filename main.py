import os
import time
import json
import unicodedata
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 設定
# ★URLは「カレンダーが見える状態の長いURL」のままにしてください
BASE_URL = "https://ana-blue-hangar-tour.resv.jp/reserve/calendar.php?x=....." 
NOTIFIED_FILE = "notified_dates.txt"

# LINE Messaging API 設定
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

# ★ここが重要：ANA工場見学の固定時間割（5枠）
TARGET_TIMES = ["9:30", "10:45", "13:00", "14:15", "15:30"]

def send_line_message(message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    try:
        requests.post(LINE_API_URL, headers=headers, data=json.dumps(data))
    except Exception as e:
        print(f"LINE送信エラー: {e}")

def get_html_via_selenium(url):
    print(f"Opening Chrome... {url[:30]}...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,1024')
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(5)
        html = driver.page_source
    except Exception as e:
        print(f"Selenium Error: {e}")
        html = None
    finally:
        driver.quit()
    return html

def check_availability():
    notified_slots = []
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            notified_slots = [line.strip() for line in f.readlines()]

    found_slots = []
    new_notified_slots = []
    
    html = get_html_via_selenium(BASE_URL)
    if not html: return

    soup = BeautifulSoup(html, 'lxml')
    cells = soup.find_all('td')
    print(f"Cells found: {len(cells)}")

    for cell in cells:
        text_all = cell.get_text(strip=True)
        if not text_all: continue

        text_norm = unicodedata.normalize('NFKC', text_all)
        
        # 1. 日付の特定（セルの先頭の数字）
        day_match = re.match(r'^(\d+)', text_norm)
        if not day_match: continue
        day_str = day_match.group(1)

        # 2. 5つの時間枠を順番にチェックする（決め打ち）
        for time_str in TARGET_TIMES:
            is_avail = False
            seat_info = ""
            
            # --- パターンA: 「残数」が明記されている場合 ---
            # 正規表現: 残(\d+) + 特定の時間
            # 例: "残113:00" -> "1"と"13:00"に分解（13の先頭を食わない）
            pattern_zan = re.compile(f'残(\d+){time_str}')
            match_zan = pattern_zan.search(text_norm)
            
            if match_zan:
                seats = int(match_zan.group(1))
                if seats >= 1:
                    is_avail = True
                    seat_info = f"残り{seats}席"
            
            # --- パターンB: 残数は書いてないが「○」「△」がある場合 ---
            # 数字パース失敗時の保険、または「余裕あり」の表記対策
            if not is_avail:
                # 時間の「直前」に記号があるかチェック
                # 簡易的に、時間の前10文字以内を見る
                idx = text_norm.find(time_str)
                if idx != -1:
                    sub_text = text_norm[max(0, idx-10):idx]
                    if "○" in sub_text or "◎" in sub_text:
                        is_avail = True
                        seat_info = "余裕あり(○)"
                    elif "△" in sub_text:
                        is_avail = True
                        seat_info = "残りわずか(△)"

            # --- 検出されたらリストに追加 ---
            if is_avail:
                display_text = f"【{day_str}日 {time_str}】 {seat_info}"
                print(f"  -> MATCH! Found: {display_text}")

                today = datetime.now().strftime("%Y-%m-%d")
                # 重複防止キー: 日付 + 時間 + 席情報
                unique_key = f"{today}: {day_str} {time_str} {seat_info}"
                
                if not any(unique_key in s for s in notified_slots if s.startswith(today)):
                    found_slots.append(display_text)
                    new_notified_slots.append(unique_key)

    if found_slots:
        print(f"Found {len(found_slots)} slots.")
        msg = "✈️ ANA工場見学 空き発生！\n\n" + "\n".join(found_slots) + f"\n\n予約: {BASE_URL}"
        send_line_message(msg)
        
        with open(NOTIFIED_FILE, "a") as f:
            for s in new_notified_slots: f.write(s + "\n")
    else:
        print("No availability found.")

if __name__ == "__main__":
    check_availability()
