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

LINE_NOTIFY_TOKEN = os.environ.get('LINE_NOTIFY_TOKEN')
TARGET_URL = "https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month=12&numberOfPeople=2&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year=2025&sfdcIFrameOrigin=null"

def send_line_notify(message):
    try:
        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
        data = {"message": message}
        requests.post(url, headers=headers, data=data)
    except:
        pass

def check_availability():
    print("--- 監視開始 ---")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"URLへアクセス中: {TARGET_URL}")
        driver.get(TARGET_URL)

        # 待機
        wait = WebDriverWait(driver, 30)
        
        # ページの状態をログに出力（ここが重要）
        print("--------------------------------------------------")
        print(f"【現在開いているページ】")
        print(f"URL: {driver.current_url}")
        print(f"タイトル: {driver.title}")
        print("--------------------------------------------------")

        # カレンダーがあるか確認
        try:
            calendar_table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
            print("カレンダー(tStyleC)は見つかりました。")
            
            # 空き枠チェック
            available_slots = calendar_table.find_elements(By.CLASS_NAME, "staHav")
            
            if len(available_slots) > 0:
                print(f"★空き枠発見！({len(available_slots)}箇所)")
                send_line_notify(f"\nJAL工場見学の空きが出ました！\n{TARGET_URL}")
            else:
                print("空き枠は見つかりませんでした（staHavなし）。")
                # 念のためHTMLの一部を表示して、本当にカレンダーが見えているか確認
                print("\n▼▼▼ HTMLソース確認（tStyleCの中身） ▼▼▼")
                print(calendar_table.get_attribute('innerHTML')[:2000]) # 最初の2000文字を表示
                print("▲▲▲ HTMLソース確認終了 ▲▲▲")

        except:
            print("【異常】カレンダーが見つかりません。")
            print("▼▼▼ 現在のページ全体のHTMLを表示します ▼▼▼")
            print(driver.page_source[:4000]) # ページ全体の最初の4000文字を表示
            print("▲▲▲ HTML終わり ▲▲▲")

    except Exception as e:
        print(f"エラー発生: {e}")
        
    finally:
        driver.quit()
        print("--- 監視終了 ---")

if __name__ == "__main__":
    if not LINE_NOTIFY_TOKEN:
        print("Error: LINE_NOTIFY_TOKEN is missing.")
    else:
        check_availability()
