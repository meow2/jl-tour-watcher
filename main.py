import os
import time
import json
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime
import re

# Selenium関連のインポート
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 設定
# ★ここに「ブラウザで見えている正しいURL」を入れてください
BASE_URL = "https://ana-blue-hangar-tour.resv.jp/reserve/calendar.php" 
NOTIFIED_FILE = "notified_dates.txt"

# LINE Messaging API 設定
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

def send_line_message(message):
    import requests # LINE送信だけはrequestsを使うのでインポート
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
    
    # Chromeのオプション設定（GitHub Actionsで動かすための必須設定）
    options = Options()
    options.add_argument('--headless') # 画面を表示しない
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,1024')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(url)
        
        # ★最重要: JavaScriptがカレンダーを描画するまで待つ
        # 5秒待機（ネットワークが遅い場合を考慮して長めに）
        time.sleep(5)
        
        # 描画後のHTMLを取得
        html = driver.page_source
        
        # デバッグ: タイトル確認
        print(f"Page Title: {driver.title}")
        
    except Exception as e:
        print(f"Selenium Error: {e}")
        html = None
    finally:
        driver.quit()
        
    return html

def check_availability():
    # 通知済みリスト読み込み
    notified_slots = []
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            notified_slots = [line.strip() for line in f.readlines()]

    found_slots = []
    new_notified_slots = []
    
    # SeleniumでHTMLを取得
    html = get_html_via_selenium(BASE_URL)
    if not html:
        return

    soup = BeautifulSoup(html, 'lxml')
    
    # カレンダーのセル(td)を取得
    cells = soup.find_all('td')
    print(f"Cells found: {len(cells)}") # デバッグ用

    for cell in cells:
        text_all = cell.get_text(strip=True)
        if not text_all: continue

        text_norm = unicodedata.normalize('NFKC', text_all)
        
        # デバッグ: 日付っぽいセルの中身を表示してみる
        if "月" in text_norm and ("○" in text_norm or "×" in text_norm or "満" in text_norm):
             print(f"[Check] {text_norm}")

        is_avail = False
        
        # 判定ロジック
        if "○" in text_norm or "◎" in text_norm or "△" in text_norm:
            is_avail = True
        
        if not is_avail:
            # 数字判定 (1席以上)
            match_zan = re.search(r'残(\d+)', text_norm)
            if match_zan:
                if int(match_zan.group(1)) >= 1:
                    is_avail = True
            else:
                link = cell.find('a')
                if link:
                    link_text = unicodedata.normalize('NFKC', link.get_text(strip=True))
                    nums = re.findall(r'\d+', link_text)
                    for n in nums:
                        # 1〜99席なら反応させる
                        if 1 <= int(n) < 100:
                            is_avail = True

        if is_avail:
            print(f"  -> MATCH! Found: {text_norm}")
            clean_text = text_norm.replace('\n', ' ').strip()
            today = datetime.now().strftime("%Y-%m-%d")
            unique_key = f"{today}: {clean_text}"
            
            if not any(unique_key in s for s in notified_slots if s.startswith(today)):
                found_slots.append(clean_text)
                new_notified_slots.append(unique_key)

    if found_slots:
        print(f"Found {len(found_slots)} slots.")
        msg = "✈️ ANA工場見学 空きあり(1席以上)\n\n" + "\n".join(found_slots) + f"\n\n予約: {BASE_URL}"
        send_line_message(msg)
        with open(NOTIFIED_FILE, "a") as f:
            for s in new_notified_slots: f.write(s + "\n")
    else:
        print("No availability found.")

if __name__ == "__main__":
    check_availability()
