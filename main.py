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

# 環境変数から設定を取得
LINE_NOTIFY_TOKEN = os.environ.get('LINE_NOTIFY_TOKEN')

# 監視対象のURL（12月、2名、車椅子不要）
TARGET_URL = "https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month=12&numberOfPeople=2&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year=2025&sfdcIFrameOrigin=null"

def send_line_notify(message):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    requests.post(url, headers=headers, data=data)

def check_availability():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"Accessing: {TARGET_URL}")
        driver.get(TARGET_URL)

        # カレンダーのテーブルが表示されるまで待機（最大30秒）
        # HTML解析結果: カレンダーは <table class="tStyleC"> です
        wait = WebDriverWait(driver, 30)
        calendar_table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
        
        # 念のため少し待つ
        time.sleep(5)

        # カレンダーテーブルの中にある画像(img)をすべて取得
        # ※ページ全体から探すと「凡例」の○△に反応してしまうため、必ず table 内から探す
        imgs = calendar_table.find_elements(By.TAG_NAME, "img")
        
        found_availability = False
        available_marks = ["○", "△"] # 空きを表す記号

        for img in imgs:
            alt_text = img.get_attribute("alt")
            
            # 1. ○か△があるか
            if alt_text in available_marks:
                found_availability = True
                print(f"空き枠発見: {alt_text}")
                break
            
            # 2. 数字（残り席数）が表示されている場合（例: "5", "4" など）
            # HTML解析結果: 残りわずかな場合、alt="5" のようになる可能性があります
            if alt_text and alt_text.isdigit():
                if int(alt_text) > 0:
                    found_availability = True
                    print(f"空き枠発見(残り{alt_text}席)")
                    break

        if found_availability:
            print("空き枠が見つかりました！")
            message = f"\nJAL工場見学の空きが出ました！\n急いで予約してください！\n{TARGET_URL}"
            send_line_notify(message)
        else:
            print("空き枠は見つかりませんでした。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        # デバッグ用: エラー時のソースを確認したい場合は以下を有効化
        # print(driver.page_source)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    if not LINE_NOTIFY_TOKEN:
        print("Error: LINE_NOTIFY_TOKEN is not set.")
    else:
        check_availability()
