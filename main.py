import os
import time
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Secrets
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_NOTIFY_TOKEN')
LINE_GROUP_ID = os.environ.get('LINE_GROUP_ID')

# 通知済みデータを管理するファイル名
HISTORY_FILE = "notified_dates.txt"

# 時間帯マッピング
TIME_SLOTS = ["09:30", "10:45", "12:50", "13:00", "13:30", "14:45", "16:30"]

def get_target_url():
    """現在の翌月のURLを生成する"""
    now = datetime.datetime.now()
    if now.month == 12:
        next_year = now.year + 1
        next_month = 1
    else:
        next_year = now.year
        next_month = now.month + 1
    
    url = f"https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month={next_month}&numberOfPeople=2&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year={next_year}&sfdcIFrameOrigin=null"
    print(f"監視対象年月: {next_year}年{next_month}月")
    print(f"URL: {url}")
    return url

def load_notified_ids():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_notified_id(new_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(new_id + "\n")

def send_line_notify(message_text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "to": LINE_GROUP_ID,
        "messages": [{"type": "text", "text": message_text}]
    }
    
    for i in range(3):
        try:
            res = requests.post(url, headers=headers, json=data, timeout=10)
            res.raise_for_status()
            print("LINE通知を送信しました。")
            return
        except Exception as e:
            print(f"LINE送信エラー(試行 {i+1}): {e}")
            time.sleep(2)
    print("LINE送信に失敗しました。")

def check_availability():
    print("--- 監視開始 ---")
    notified_ids = load_notified_ids()
    print(f"通知済みID数: {len(notified_ids)}")

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    target_url = get_target_url()

    try:
        driver.get(target_url)
        wait = WebDriverWait(driver, 30)
        
        # カレンダー枠の出現を待つ
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
        
        # 【追加】一番下までスクロールして、遅延読み込み要素を描画させる
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # 【修正】待機時間を長くする（3秒→10秒）
        print("ページ読み込み待機中(10秒)...")
        time.sleep(10)

        tables = driver.find_elements(By.CLASS_NAME, "tStyleC")
        print(f"ページ内に {len(tables)} 個のカレンダーが見つかりました。")

        new_slots_msg = []
        found_count = 0
        
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            current_date_text = "日付不明"

            for row in rows:
                ths = row.find_elements(By.TAG_NAME, "th")
                if ths:
                    text = ths[0].text.strip()
                    if "コース" not in text and text != "": 
                        current_date_text = text
                
                tds = row.find_elements(By.TAG_NAME, "td")
                if not tds: continue

                course_name = tds[0].text.strip().replace("\n", " ")
                
                for i in range(1, len(tds)):
                    cell = tds[i]
                    time_str = TIME_SLOTS[i-1] if (i-1) < len(TIME_SLOTS) else "時間不明"

                    # staHav（空き）クラスを探す
                    if cell.find_elements(By.CLASS_NAME, "staHav"):
                        found_count += 1
                        try:
                            icon_alt = cell.find_element(By.TAG_NAME, "img").get_attribute("alt")
                        except:
                            icon_alt = "空き"

                        slot_id = f"{current_date_text}_{time_str}_{course_name}_{icon_alt}"
                        
                        if slot_id not in notified_ids:
                            msg = f"📅 {current_date_text}\n⏰ {time_str} : {icon_alt}\n🏭 {course_name}"
                            new_slots_msg.append(msg)
                            save_notified_id(slot_id)
                            notified_ids.add(slot_id)
                            print(f"★新規発見: {msg.replace(chr(10), ' ')}")
                        else:
                            print(f"スキップ(通知済み): {current_date_text} {time_str} {icon_alt}")

        if len(new_slots_msg) > 0:
            msg_body = "\n\n".join(new_slots_msg)
            message = (
                f"✈️ JAL工場見学 空き発見！\n"
                f"（新着 {len(new_slots_msg)} 枠）\n\n"
                f"{msg_body}\n\n"
                f"予約URL:\n{target_url}"
            )
            if len(message) > 2000:
                message = message[:1900] + "\n...(以下省略)"
            send_line_notify(message)
        else:
            print("新規の空き枠はありませんでした。")
            if found_count == 0:
                print("【警告】空き枠(staHav)が1つも見つかりませんでした。読み込み失敗の可能性があります。")
                # デバッグ: 最初のテーブルのHTMLを出力してみる
                if len(tables) > 0:
                    print("▼▼▼ テーブルHTML抜粋 ▼▼▼")
                    print(tables[-1].get_attribute('outerHTML')[:1000])

    except Exception as e:
        print(f"エラー発生: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
        print("--- 監視終了 ---")

if __name__ == "__main__":
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("Error: Token missing")
    else:
        check_availability()
