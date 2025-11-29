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

# 設定
HISTORY_FILE = "notified_dates.txt"
REQUIRED_PEOPLE = 2
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
    
    url = f"https://jalfactorytour.my.salesforce-sites.com/rselectcourse?month={next_month}&numberOfPeople={REQUIRED_PEOPLE}&useWheelchair=%25E4%25B8%258D%25E8%25A6%2581%2BUnnecessary&year={next_year}&sfdcIFrameOrigin=null"
    print(f"監視対象: {next_year}年{next_month}月")
    return url

def load_history_with_reset_check():
    """
    ファイルから履歴を読み込む際、日付が変わっていたらリセットする
    """
    history = {}
    today_str = datetime.date.today().isoformat() # 例: "2025-12-01"

    if not os.path.exists(HISTORY_FILE):
        return history

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # ファイルが空の場合
        if not lines:
            return history

        # 1行目の日付チェック
        # 形式: LAST_RUN::2025-12-01
        first_line = lines[0].strip()
        
        if first_line.startswith("LAST_RUN::"):
            last_run_date = first_line.split("::")[1]
            if last_run_date != today_str:
                print(f"📅 日付変更を検知 (前回:{last_run_date} -> 今日:{today_str})")
                print("   通知済み履歴をリセットします。")
                return {} # 空の履歴を返す（リセット）
            else:
                print("📅 日付変更なし。履歴を引き継ぎます。")
        else:
            # ヘッダーがない（古い形式など）場合は念のためリセット
            print("⚠ ファイル形式不一致のためリセットします。")
            return {}

        # 2行目以降（データ部分）を読み込む
        for line in lines[1:]:
            if "::" in line:
                parts = line.strip().split("::")
                if len(parts) == 2:
                    history[parts[0]] = parts[1]
                    
    except Exception as e:
        print(f"履歴読み込みエラー: {e} (リセットして続行)")
        return {}

    return history

def save_history(history):
    """日付ヘッダーを付けて保存する"""
    today_str = datetime.date.today().isoformat()
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            # 1行目に日付を記録
            f.write(f"LAST_RUN::{today_str}\n")
            # 2行目以降にデータを記録
            for key, val in history.items():
                f.write(f"{key}::{val}\n")
    except Exception as e:
        print(f"履歴保存エラー: {e}")

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
    # ここで日付チェックとリセットを行う
    current_history = load_history_with_reset_check()
    print(f"保持履歴データ数: {len(current_history)}")

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    target_url = get_target_url()

    new_slots_msg = []

    try:
        driver.get(target_url)
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tStyleC")))
        
        # スクロールして描画
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        print("ページ読み込み待機中(10秒)...")
        time.sleep(10)

        tables = driver.find_elements(By.CLASS_NAME, "tStyleC")
        print(f"ページ内に {len(tables)} 個のカレンダーが見つかりました。")

        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            current_date_text = "日付不明"

            for row in rows:
                # 日付取得
                ths = row.find_elements(By.TAG_NAME, "th")
                if ths:
                    text = ths[0].text.strip()
                    if "コース" not in text and text != "": 
                        current_date_text = text
                
                # コース取得
                tds = row.find_elements(By.TAG_NAME, "td")
                if not tds: continue

                course_name = tds[0].text.strip().replace("\n", " ")
                
                # 時間枠の確認
                for i in range(1, len(tds)):
                    cell = tds[i]
                    time_str = TIME_SLOTS[i-1] if (i-1) < len(TIME_SLOTS) else "時間不明"

                    if cell.find_elements(By.CLASS_NAME, "staHav"):
                        try:
                            img = cell.find_element(By.TAG_NAME, "img")
                            icon_alt = img.get_attribute("alt").strip()
                        except:
                            icon_alt = "空き"

                        # 人数チェック(2名以上)
                        is_bookable = False
                        if icon_alt in ['○', '△', '◎']:
                            is_bookable = True
                        elif icon_alt.isdigit():
                            if int(icon_alt) >= REQUIRED_PEOPLE:
                                is_bookable = True
                        
                        if is_bookable:
                            slot_key = f"{current_date_text}_{time_str}_{course_name}"
                            
                            # 履歴と比較（まだない、または状態が変わった）
                            if (slot_key not in current_history) or (current_history[slot_key] != icon_alt):
                                msg = f"📅 {current_date_text}\n⏰ {time_str} : {icon_alt}\n🏭 {course_name}"
                                new_slots_msg.append(msg)
                                print(f"★状態変化・新規: {msg.replace(chr(10), ' ')}")
                                current_history[slot_key] = icon_alt
                            else:
                                print(f"スキップ(通知済み): {current_date_text} {time_str} {icon_alt}")

        if len(new_slots_msg) > 0:
            msg_body = "\n\n".join(new_slots_msg)
            message = (
                f"✈️ JAL工場見学 空き変動あり！\n"
                f"（{len(new_slots_msg)} 件の更新）\n\n"
                f"{msg_body}\n\n"
                f"予約URL:\n{target_url}"
            )
            if len(message) > 1900:
                message = message[:1900] + "\n...(以下省略)"
            
            send_line_notify(message)
        else:
            print("空き状況に変化はありませんでした。")
            
        save_history(current_history)

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
