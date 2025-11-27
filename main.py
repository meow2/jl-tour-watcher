import os
import time
import json
import unicodedata
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 設定
BASE_URL = "https://ana-blue-hangar-tour.resv.jp/reserve/calendar.php"
NOTIFIED_FILE = "notified_dates.txt"
TARGET_TIMES = ["9:30", "10:45", "13:00", "14:15", "15:30"]
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

# LINE Messaging API 設定
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

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

def parse_html(html, notified_slots, found_slots, new_notified_slots):
    """HTMLから空き情報を抽出する"""
    soup = BeautifulSoup(html, 'lxml')
    
    # --- 1. まず「今、何年の何月を表示しているか」を取得 ---
    # id="period_area" の中身 (例: "2025年11月") を探す
    period_area = soup.find(id="period_area")
    current_year = 0
    current_month = 0
    
    if period_area:
        period_text = period_area.get_text(strip=True)
        # "2025年11月" から数字を抜き出す
        m = re.search(r'(\d+)年(\d+)月', period_text)
        if m:
            current_year = int(m.group(1))
            current_month = int(m.group(2))
            print(f"  [Info] Calendar is showing: {current_year}年 {current_month}月")
    
    if current_year == 0:
        print("  [Error] Could not identify Year/Month from header.")
        return # 年月が取れないと曜日計算できないのでスキップ

    cells = soup.find_all('td')
    print(f"  -> Cells found: {len(cells)}")

    for cell in cells:
        text_all = cell.get_text(strip=True)
        if not text_all: continue

        text_norm = unicodedata.normalize('NFKC', text_all)
        
        # --- 2. 日付特定 ---
        day_match = re.match(r'^(\d+)', text_norm)
        if not day_match: continue
        day_val = int(day_match.group(1))

        # --- 3. 曜日を計算 ---
        try:
            # datetimeオブジェクト作成
            target_date = date(current_year, current_month, day_val)
            # 曜日取得 (0=月, 6=日)
            wd_str = WEEKDAYS[target_date.weekday()]
        except ValueError:
            # ありえない日付（2月30日など）の場合の安全策
            continue

        # --- 4. 時間枠チェック ---
        for time_str in TARGET_TIMES:
            is_avail = False
            seat_info = ""
            
            # パターンA: 残数明記
            pattern_zan = re.compile(f'残(\d+){time_str}')
            match_zan = pattern_zan.search(text_norm)
            
            if match_zan:
                seats = int(match_zan.group(1))
                if seats >= 1:
                    is_avail = True
                    seat_info = f"残り{seats}席"
            
            # パターンB: 記号
            if not is_avail:
                idx = text_norm.find(time_str)
                if idx != -1:
                    sub_text = text_norm[max(0, idx-10):idx]
                    if "○" in sub_text or "◎" in sub_text:
                        is_avail = True
                        seat_info = "余裕あり(○)"
                    elif "△" in sub_text:
                        is_avail = True
                        seat_info = "残りわずか(△)"

            if is_avail:
                # 表示テキストを作成： 【11月28日(金) 9:30】
                display_text = f"【{current_month}月{day_val}日({wd_str}) {time_str}】 {seat_info}"
                print(f"    MATCH! Found: {display_text}")

                # ユニークキー： 年月日を含めて一意にする
                # 例: "2025-11-28 9:30 残り1席"
                # これにより、同じ日時でも席数が変われば再度通知されるか、
                # あるいは「席数」をキーから外せば「一度通知したらその回は無視」になる。
                # ここでは「日付+時間+席数」をキーにする（席数が減ったらまた通知してしまうのを防ぐため、席数はキーに含めない方がいいかも？
                # 要望「一度通知したらその日は通知しない」に従い、席数はキーに含めず、日時だけで管理します。
                
                unique_key_date = f"{current_year}-{current_month}-{day_val} {time_str}"
                
                # 今日の日付（実行日）をキーの先頭につけることで「明日になればまた通知する」を実現
                today_exec = datetime.now().strftime("%Y-%m-%d")
                unique_key = f"{today_exec} -> {unique_key_date}"
                
                if not any(unique_key in s for s in notified_slots if s.startswith(today_exec)):
                    if display_text not in found_slots:
                        found_slots.append(display_text)
                        new_notified_slots.append(unique_key)

def check_availability():
    print("Starting check...")
    
    # 通知履歴読み込み
    notified_slots = []
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            notified_slots = [line.strip() for line in f.readlines()]

    found_slots = []
    new_notified_slots = []

    # Selenium設定
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,1024')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # --- 1ページ目 ---
        print(f"Loading page 1... {BASE_URL[:30]}...")
        driver.get(BASE_URL)
        time.sleep(5)
        
        print("Parsing page 1...")
        parse_html(driver.page_source, notified_slots, found_slots, new_notified_slots)
        
        # --- 2ページ目 ---
        try:
            print("Looking for Next Month button (#next a)...")
            next_btns = driver.find_elements(By.CSS_SELECTOR, "#next a")
            
            if next_btns:
                print("Clicking Next Month button...")
                driver.execute_script("arguments[0].click();", next_btns[0])
                time.sleep(5)
                
                print("Parsing page 2...")
                parse_html(driver.page_source, notified_slots, found_slots, new_notified_slots)
            else:
                print("Next Month button not found.")
                
        except Exception as e:
            print(f"Could not move to next month: {e}")

    except Exception as e:
        print(f"Selenium Error: {e}")
    finally:
        driver.quit()

    # 通知処理
    if found_slots:
        print(f"Total slots found: {len(found_slots)}")
        
        # リストが見やすいようにソート（日付順）する処理を入れるとベターですが
        # 現状は取得順（カレンダー順）なのでそのままでも概ね綺麗です
        
        msg = "✈️ ANA工場見学 空き発生！\n\n" + "\n".join(found_slots) + f"\n\n予約: {BASE_URL}"
        send_line_message(msg)
        
        with open(NOTIFIED_FILE, "a") as f:
            for s in new_notified_slots: f.write(s + "\n")
    else:
        print("No availability found.")

if __name__ == "__main__":
    check_availability()
