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

# GitHub ActionsのSecretsからLINEトークンを取得
LINE_NOTIFY_TOKEN = os.environ.get('LINE_NOTIFY_TOKEN')

# 監視対象URL
TARGET_URL = "https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month=12&numberOfPeople=2&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year=2025&sfdcIFrameOrigin=null"

def send_line_notify(message):
    print(f"LINE送信開始: {message}")
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    try:
        res = requests.post(url, headers=headers, data=data)
        print(f"LINE送信結果: {res.status_code} {res.text}")
    except Exception as e:
        print(f"LINE送信エラー: {e}")

def check_availability():
    print("--- 監視開始 ---")
    options = Options()
    options.add_argument('--headless') # ヘッドレスモード（画面なし）
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # 一般的なブラウザに見せかける
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"URLへアクセス中: {TARGET_URL}")
        driver.get(TARGET_URL)

        # カレンダーのテーブル(class="tStyleC")が表示されるまで待つ（最大30秒）
        wait = WebDriverWait(driver, 30)
        calendar_table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
        
        # 念のため描画待ち
        time.sleep(3)

        # 【判定ロジック】
        # カレンダーテーブルの中に、class="staHav" (Status Have = 空きあり) を持つ要素があるか探す
        # ※凡例（Legend）は別の場所にあるので、calendar_table以下を探せば誤検知しない
        
        available_slots = calendar_table.find_elements(By.CLASS_NAME, "staHav")
        
        if len(available_slots) > 0:
            print(f"★空き枠を {len(available_slots)} 箇所発見しました！")
            
            # 念のため、見つけた枠の中身（日付や時間帯など）を少しログに出す
            try:
                first_slot_text = available_slots[0].find_element(By.XPATH, "./..").text
                print(f"検出サンプル: {first_slot_text}")
            except:
                pass

            message = (
                f"\n✈️ JAL工場見学の空きが出ました！\n"
                f"現在の空き枠数: {len(available_slots)}箇所\n"
                f"急いで予約してください！\n"
                f"{TARGET_URL}"
            )
            send_line_notify(message)
        else:
            print("空き枠は見つかりませんでした（staHavクラスなし）。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        # 詳細なエラー情報を出す
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()
        print("--- 監視終了 ---")

if __name__ == "__main__":
    if not LINE_NOTIFY_TOKEN:
        print("Error: LINE_NOTIFY_TOKEN が設定されていません。Settings > Secrets を確認してください。")
    else:
        check_availability()
