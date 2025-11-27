import os
import requests
import json
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime
import re

# 設定
BASE_URL = "https://ana-blue-hangar-tour.resv.jp/reserve/calendar.php"
NOTIFIED_FILE = "notified_dates.txt"

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
    except Exception:
        pass

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'lxml')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def check_availability():
    # 通知済みリスト読み込み
    notified_slots = []
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            notified_slots = [line.strip() for line in f.readlines()]

    found_slots = []
    new_notified_slots = []
    
    # URLリスト作成
    urls = [BASE_URL]
    soup = get_soup(BASE_URL)
    if soup:
        next_link = soup.find('a', string=re.compile(r'次月|翌月|Next'))
        if next_link and next_link.get('href'):
            href = next_link.get('href')
            if not href.startswith('http'):
                urls.append("https://ana-blue-hangar-tour.resv.jp/reserve/" + href)

    print(f"Checking URLs: {urls}")
    
    for url in urls:
        soup = get_soup(url)
        if not soup: continue
        
        # サイト内の全ての日付セル(td)を取得
        cells = soup.find_all('td')
        
        for cell in cells:
            # 日付セルかどうかの簡易チェック（数字やリンクが含まれるか）
            text_all = cell.get_text(strip=True)
            if not text_all: continue

            # 正規化（全角数字を半角にするなど）
            text_norm = unicodedata.normalize('NFKC', text_all)
            
            # ログ出し（デバッグ用：何が見えているか確認）
            # あまりに長いログは省略
            if len(text_norm) < 50 and ("月" in text_norm or "日" in text_norm or "空" in text_norm or "残" in text_norm):
                print(f"[Check] Cell content: {text_norm}")

            is_avail = False
            
            # --- 判定ロジック ---
            
            # 1. 記号判定 (○, ◎, △)
            if "○" in text_norm or "◎" in text_norm or "△" in text_norm:
                is_avail = True
            
            # 2. 数字判定 (1席以上)
            # "残1" "1席" などの数字を拾う
            if not is_avail:
                # 日付の数字(1~31)を誤検知しないための工夫
                # 通常、日付はセルの先頭にあるが、残席数はリンクテキスト内や「残」の後ろにあることが多い
                
                # "残X" のパターンを探す
                match_zan = re.search(r'残(\d+)', text_norm)
                if match_zan:
                    seats = int(match_zan.group(1))
                    if seats >= 1:
                        is_avail = True
                else:
                    # 単純にリンク内の数字を探す（日付リンクを除外したい）
                    # リンクがある場合のみチェック
                    link = cell.find('a')
                    if link:
                        link_text = unicodedata.normalize('NFKC', link.get_text(strip=True))
                        # リンクテキスト内の数字を抽出
                        nums = re.findall(r'\d+', link_text)
                        for n in nums:
                            val = int(n)
                            # 日付の数字(1~31)と区別がつかない場合があるが、
                            # 予約サイトは「日付リンク」と「申込リンク」が別、または一緒になっている。
                            # ここでは「現在日より未来」かつ「数字がある」なら候補とするが、
                            # 誤検知覚悟で「数字があれば反応」させてみる（まずは取得できるか確認のため）
                            if val >= 1 and val <= 100: # 100席以上は稀なので誤検知防止フィルタ
                                # 日付そのものではないか確認（簡易）：テキスト全体にその数字以外に要素があるか
                                # (これは難しいので、一旦「リンク内の数字」はすべて空き席候補とみなす)
                                is_avail = True

            if is_avail:
                print(f"  -> MATCH! Found candidate: {text_norm}")
                
                # 整形してリスト追加
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
