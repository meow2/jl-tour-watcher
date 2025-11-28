import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Secretsから取得（トークンとグループID）
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_NOTIFY_TOKEN') # 名前は流用
LINE_GROUP_ID = os.environ.get('LINE_GROUP_ID') # 新しく作ったSecret

# 監視対象URL（基本URL）
TARGET_URL = "https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month=12&numberOfPeople=2&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year=2025&sfdcIFrameOrigin=null"

# 時間帯マッピング
TIME_SLOTS = ["09:30", "10:45", "12:50", "13:00", "13:30", "14:45", "16:30"]

def send_line_notify(message_text):
    """Messaging APIを使ってPushメッセージを送る"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    # PushメッセージのJSON構造
    data = {
        "to": LINE_GROUP_ID,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }
    
    max_retries = 3
    for i in range(max_retries):
        try:
            # json=data とすることで自動的にJSON形式で送られる
            res = requests.post(url, headers=headers, json=data, timeout=10)
            res.raise_for_status()
            print("LINE通知(Messaging API)を送信しました。")
            return
        except Exception as e:
            print(f"LINE送信エラー(試行 {i+1}/{max_retries}): {e}")
            if "400" in str(e) or "401" in str(e):
                print("認証エラーまたはIDエラーです。TokenとGroupIDを確認してください。")
                break
            time.sleep(2)
    
    print("LINE送信に失敗しました。")

def check_availability():
    print("--- 監視開始 ---")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"URLへアクセス中: {TARGET_URL}")
        driver.get(TARGET_URL)

        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
        time.sleep(3)

        tables = driver.find_elements(By.CLASS_NAME, "tStyleC")
        print(f"ページ内に {len(tables)} 個のカレンダーが見つかりました。")

        found_slots = []

        for table in tables:
            try:
                month_title = table.find_element(By.XPATH, "preceding-sibling::h5[1]").text.strip()
            except:
                month_title = "不明な月"

            rows = table.find_elements(By.TAG_NAME, "tr")
            current_date_text = "日付不明"

            for row in rows:
                ths = row.find_elements(By.TAG_NAME, "th")
                if ths:
                    text = ths[0].text.strip()
                    if "コース" not in text and text != "": 
                        current_date_text = text
                
                tds = row.find_elements(By.TAG_NAME, "td")
                if not tds:
                    continue 

                course_name = tds[0].text.strip().replace("\n", " ")
                
                for i in range(1, len(tds)):
                    cell = tds[i]
                    time_str = TIME_SLOTS[i-1] if (i-1) < len(TIME_SLOTS) else "時間不明"

                    if cell.find_elements(By.CLASS_NAME, "staHav"):
                        try:
                            icon_alt = cell.find_element(By.TAG_NAME, "img").get_attribute("alt")
                        except:
                            icon_alt = "空き"

                        slot_info = f"📅 {month_title} {current_date_text}\n⏰ {time_str} : {icon_alt}\n🏭 {course_name}"
                        found_slots.append(slot_info)
                        print(f"★発見: {slot_info.replace(chr(10), ' ')}")

        if len(found_slots) > 0:
            msg_body = "\n\n".join(found_slots)
            message = (
                f"✈️ JAL工場見学 空き発見！\n"
                f"（計 {len(found_slots)} 枠）\n\n"
                f"{msg_body}\n\n"
                f"予約URL:\n{TARGET_URL}"
            )
            # 文字数制限対策
            if len(message) > 2000:
                message = message[:1900] + "\n...(以下省略)"
            
            send_line_notify(message)
        else:
            print("空き枠は見つかりませんでした。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()
        print("--- 監視終了 ---")

if __name__ == "__main__":
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("Error: LINE_NOTIFY_TOKEN (Channel Access Token) is missing.")
    elif not LINE_GROUP_ID:
        print("Error: LINE_GROUP_ID is missing.")
    else:
        check_availability()
