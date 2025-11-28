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
    except Exception as e:
        print(f"LINE送信エラー: {e}")

def check_availability():
    print("--- 監視開始 ---")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # ウィンドウサイズを大きくしておく（レスポンシブで表示が消えるのを防ぐ）
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"URLへアクセス中: {TARGET_URL}")
        driver.get(TARGET_URL)

        # 30秒待機
        wait = WebDriverWait(driver, 30)
        
        # デバッグ用：タイトル表示
        print(f"ページタイトル: {driver.title}")

        # カレンダーテーブルの出現を待つ
        try:
            calendar_table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
            print("カレンダーテーブル(tStyleC)を発見しました。")
        except:
            print("【警告】カレンダーテーブルが見つかりません。ロード中か、別ページに飛ばされています。")
            raise Exception("Calendar table not found")

        time.sleep(5) # 描画待ち

        # HTMLソース全体の取得（デバッグ保存用）
        html_source = driver.page_source
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html_source)
        
        # スクリーンショット撮影
        driver.save_screenshot("debug_screenshot.png")
        print("デバッグ用ファイル(html, png)を保存しました。")

        # 判定ロジック
        available_slots = calendar_table.find_elements(By.CLASS_NAME, "staHav")
        
        # デバッグ：テーブル内のテキストを少し出力してみる
        print(f"テーブル内のテキスト抜粋: {calendar_table.text[:200].replace(chr(10), ' ')}...")

        if len(available_slots) > 0:
            print(f"★空き枠を {len(available_slots)} 箇所発見！")
            send_line_notify(f"\nJAL工場見学の空きが出ました！({len(available_slots)}箇所)\n{TARGET_URL}")
        else:
            print("空き枠は見つかりませんでした（staHavクラスなし）。")
            # 念のため、staNon（満席）があるか確認してログに出す
            full_slots = calendar_table.find_elements(By.CLASS_NAME, "staNon")
            print(f"参考: 満席枠(staNon)は {len(full_slots)} 箇所見つかりました。")

    except Exception as e:
        print(f"エラー発生: {e}")
        # エラー時もスクショを撮る
        driver.save_screenshot("error_screenshot.png")
        with open("error_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    finally:
        driver.quit()
        print("--- 監視終了 ---")

if __name__ == "__main__":
    if not LINE_NOTIFY_TOKEN:
        print("Error: LINE_NOTIFY_TOKEN is missing.")
    else:
        check_availability()
