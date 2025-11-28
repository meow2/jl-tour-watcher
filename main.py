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
# 月のパラメータは指定してもページ内で上書きされる可能性があるため、基本URLを使用
TARGET_URL = "https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month=12&numberOfPeople=2&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year=2025&sfdcIFrameOrigin=null"

# 列インデックスと時間の対応表 (HTML構造に基づく)
# td[0]=コース名, td[1]=09:30, td[2]=10:45 ...
TIME_SLOTS = ["09:30", "10:45", "12:50", "13:00", "13:30", "14:45", "16:30"]

def send_line_notify(message):
    try:
        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
        data = {"message": message}
        requests.post(url, headers=headers, data=data)
        print("LINE通知を送信しました。")
    except Exception as e:
        print(f"LINE送信エラー: {e}")

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
        # いずれかのカレンダーが表示されるまで待つ
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
        time.sleep(3)

        # ページ内のすべてのカレンダーテーブルを取得（11月、12月...）
        tables = driver.find_elements(By.CLASS_NAME, "tStyleC")
        print(f"ページ内に {len(tables)} 個のカレンダーが見つかりました。")

        found_slots = []

        for table in tables:
            # そのテーブルが何月かを取得（テーブルの直前にあるh5タグ）
            try:
                month_title = table.find_element(By.XPATH, "preceding-sibling::h5[1]").text.strip()
            except:
                month_title = "不明な月"

            # 行（tr）を走査
            rows = table.find_elements(By.TAG_NAME, "tr")
            current_date_text = "日付不明"

            for row in rows:
                # --- 1. 日付の取得 (th) ---
                # rowspanがあるため、thがない行は前の行の日付を引き継ぐ
                ths = row.find_elements(By.TAG_NAME, "th")
                if ths:
                    # 日付セルがある場合、更新
                    # ただし、ヘッダー行（"コース"などが書いてある行）を除く
                    text = ths[0].text.strip()
                    if "コース" not in text and text != "": 
                        current_date_text = text
                
                # --- 2. コース名と空き状況の確認 (td) ---
                tds = row.find_elements(By.TAG_NAME, "td")
                if not tds:
                    continue # tdがない行（ヘッダー行など）はスキップ

                # 最初のtdはコース名
                course_name = tds[0].text.strip().replace("\n", " ")
                
                # 残りのtdは時間枠（TIME_SLOTSに対応）
                # tds[1] -> 09:30, tds[2] -> 10:45 ...
                for i in range(1, len(tds)):
                    cell = tds[i]
                    time_str = TIME_SLOTS[i-1] if (i-1) < len(TIME_SLOTS) else "時間不明"

                    # --- 3. 空き判定 (staHavクラスを持つ要素があるか) ---
                    # <a>タグまたは<span>タグに class="staHav" が付いているか確認
                    if cell.find_elements(By.CLASS_NAME, "staHav"):
                        
                        # 空きマークの種類を取得（○, △, 数字など）
                        try:
                            icon_alt = cell.find_element(By.TAG_NAME, "img").get_attribute("alt")
                        except:
                            icon_alt = "空き"

                        slot_info = f"📅 {month_title} {current_date_text}\n⏰ {time_str} : {icon_alt}\n🏭 {course_name}"
                        found_slots.append(slot_info)
                        print(f"★発見: {slot_info.replace(chr(10), ' ')}")

        # 通知処理
        if len(found_slots) > 0:
            # LINE通知は見やすく整形
            msg_body = "\n\n".join(found_slots)
            message = (
                f"\n✈️ JAL工場見学の空きが出ました！\n"
                f"（合計 {len(found_slots)} 枠）\n\n"
                f"{msg_body}\n\n"
                f"予約はこちら急げ！:\n{TARGET_URL}"
            )
            # メッセージが長すぎる場合はカットする処理（LINE制限対策）
            if len(message) > 1000:
                message = message[:900] + "\n\n...(他多数のため省略)..."
                
            send_line_notify(message)
        else:
            print("空き枠は見つかりませんでした（全期間チェック済み）。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()
        print("--- 監視終了 ---")

if __name__ == "__main__":
    if not LINE_NOTIFY_TOKEN:
        print("Error: LINE_NOTIFY_TOKEN is missing.")
    else:
        check_availability()
