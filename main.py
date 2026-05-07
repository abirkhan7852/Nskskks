import requests
import time
import threading
import json
import os
import re

# --- কনফিগারেশন ---
TELEGRAM_TOKEN = "8624534058:AAFVp1nm4xCGD-NfpcqusmH-ok8_0Q90fAk"
DB_FILE = "users.json"

# আপবিট এপিআই
UPBIT_MARKET_API = "https://api.upbit.com/v1/market/all"
UPBIT_NOTICE_API = "https://api-manager.upbit.com/api/v1/notices?page=1&per_page=5"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
})

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        user_ids = set(json.load(f))
else:
    user_ids = set()

old_markets = set()
tracked_notices = {}
last_update_id = 0

def save_users():
    with open(DB_FILE, "w") as f:
        json.dump(list(user_ids), f)

def send_broadcast(message):
    for chat_id in list(user_ids):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            session.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        except: pass

def convert_to_bd_time(kst_time_str):
    if not kst_time_str: return None
    try:
        kst_hour = int(kst_time_str.split(':')[0])
        minute = kst_time_str.split(':')[1]
        bd_hour = (kst_hour - 3) % 24
        ampm = "PM" if bd_hour >= 12 else "AM"
        display_hour = bd_hour if bd_hour <= 12 else bd_hour - 12
        if display_hour == 0: display_hour = 12
        return f"{display_hour}:{minute} {ampm}"
    except: return None

# --- ১. সুপার ফাস্ট মার্কেট মনিটর (Surprise Listing) ---
def fast_market_monitor():
    global old_markets
    print("⚡ Market Monitor (1.5s Interval) চালু হয়েছে...")
    try:
        res = session.get(UPBIT_MARKET_API, timeout=10).json()
        old_markets = {item['market'] for item in res}
    except: pass

    while True:
        try:
            response = session.get(UPBIT_MARKET_API, timeout=5)
            if response.status_code == 200:
                current_markets = {item['market'] for item in response.json()}
                new_listings = current_markets - old_markets
                if new_listings:
                    for market in new_listings:
                        msg = f"🔥 <b>SURPRISE LISTING!</b>\n\n💰 Pair: <code>{market}</code>\n✅ সরাসরি মার্কেটে লিস্ট হয়েছে!"
                        send_broadcast(msg)
                    old_markets = current_markets
        except: pass
        time.sleep(1.5) # ১.৫ সেকেন্ড বিরতি

# --- ২. নোটিশ ও টাইম মনিটর (Official Notice) ---
def notice_monitor():
    global tracked_notices
    print("📢 Notice Monitor চালু হয়েছে...")
    try:
        init_res = session.get(UPBIT_NOTICE_API, timeout=10).json()
        if init_res.get('success'):
            for n in init_res['data']['list']: tracked_notices[n['id']] = "SEEN"
    except: pass

    while True:
        try:
            response = session.get(UPBIT_NOTICE_API, timeout=10)
            if response.status_code == 200:
                notices = response.json().get('data', {}).get('list', [])
                for notice in notices:
                    n_id, n_title = notice['id'], notice['title']
                    if any(word in n_title.lower() for word in ["listing", "added", "market", "거래", "상장"]):
                        if n_id not in tracked_notices:
                            # নোটিশের ভেতর থেকে টাইম বের করা
                            detail = session.get(f"https://api-manager.upbit.com/api/v1/notices/{n_id}", timeout=10).json()
                            body = detail.get('data', {}).get('body', '')
                            time_match = re.search(r'(\d{2}:\d{2})', body)
                            bd_time = convert_to_bd_time(time_match.group(1)) if time_match else None
                            
                            tracked_notices[n_id] = time_match.group(1) if time_match else None
                            time_info = f"⏰ ট্রেড শুরু: <b>{bd_time} (BD)</b>" if bd_time else "⏰ ট্রেড শুরু: ঘোষণা হয়নি"
                            
                            msg = f"📢 <b>নতুন লিস্টিং নোটিশ!</b>\n\n📌 <code>{n_title}</code>\n{time_info}\n🔗 <a href='https://upbit.com/service_center/notice?id={n_id}'>বিস্তারিত</a>"
                            send_broadcast(msg)
        except: pass
        time.sleep(10) # নোটিশ ১০ সেকেন্ড পর পর চেক করলেই চলে

def telegram_listener():
    global last_update_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=20"
            res = session.get(url, timeout=25).json()
            if res.get('result'):
                for update in res['result']:
                    last_update_id = update['update_id']
                    if 'message' in update and 'text' in update['message']:
                        chat_id = update['message']['chat']['id']
                        if update['message']['text'] == "/start":
                            if chat_id not in user_ids: user_ids.add(chat_id); save_users()
                            session.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                         json={"chat_id": chat_id, "text": "✅ <b>Sniper Bot Active!</b>\nমার্কেট (১.৫ সে.) এবং নোটিশ (১০ সে.) ট্র্যাকিং চলছে।", "parse_mode": "HTML"})
        except: pass
        time.sleep(2)

threading.Thread(target=fast_market_monitor, daemon=True).start()
threading.Thread(target=notice_monitor, daemon=True).start()
telegram_listener()
