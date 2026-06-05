import requests
import time
import random
import os
import json
import re
from urllib.parse import quote
from datetime import datetime

# ==================== 配置区 ====================
INPUT_FILE = "input.txt"
HISTORY_FILE = "docs/history.json"
DATA_FILE = "docs/data.json"

STATIC_PROFILE = "aHR0cHM6Ly9ia2ltZy5jZG4uYmNlYm9zLmNvbS9zbWFydC80YjkwZjYwMzczOGRhOTc3MzkxMjhiMTkwNjBkZWYxOTg2MTgzNjdhNDVmNi1ia2ltZy1wcm9jZXNzLHZfMSxyd18xLHJoXzEsbWF4bF84MDAscGFkXzE%2FeC1iY2UtcHJvY2Vzcz1pbWFnZSUyRmZvcm1hdCUyQ2ZfYXV0byUyRnJlc2l6ZSUyQ21fZmlsbCUyQ3dfMTAwJTJDaF8xMDA%3D"

RAW_COOKIE = os.environ.get("BAIDU_COOKIE", "")
if not RAW_COOKIE:
    print("警告: 未设置 BAIDU_COOKIE 环境变量，请确保在 GitHub Secrets 中配置。")

def clean_cookie(c):
    return re.sub(r'[^\x20-\x7E]+', '', c).strip()

COOKIE_STRING = clean_cookie(RAW_COOKIE)

def build_headers(baikeid, name):
    encoded_name = quote(name, safe='')
    referer = f"https://figure.baidu.com/aladdin-landing/sendFlower?baikeid={baikeid}&name={encoded_name}"
    return {
        'authority': 'figure.baidu.com',
        'accept': '*/*',
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'cookie': COOKIE_STRING,
        'origin': 'https://figure.baidu.com',
        'referer': referer,
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    }

def fetch_data(baikeid, name):
    result = {
        "name": name,
        "id": baikeid,
        "today_gift": 0,
        "today_users": 0,
        "avg": 0,
        "total_gift": 0,
        "status": "成功"
    }
    session = requests.Session()
    url_trend = "https://figure.baidu.com/api/land/interact/getTrend"
    url_equity = "https://figure.baidu.com/api/land/interact/getEquity"

    # 今日数据
    try:
        headers = build_headers(baikeid, name)
        resp = session.post(url_trend, data=f"baikeid={baikeid}", headers=headers, timeout=10)
        if resp.status_code == 200:
            json_data = resp.json()
            if json_data.get('errno') == 0:
                data = json_data.get('data', {})
                result['today_gift'] = data.get('userGift', 0)
                result['today_users'] = data.get('userNum', 0)
                result['avg'] = round(result['today_gift'] / result['today_users'], 2) if result['today_users'] > 0 else 0
            else:
                result['status'] = f"趋势接口错误: {json_data.get('msg', '未知')}"
        else:
            result['status'] = f"趋势HTTP {resp.status_code}"
    except Exception as e:
        result['status'] = f"趋势异常: {str(e)}"

    # 累计数据
    try:
        headers = build_headers(baikeid, name)
        encoded_name = quote(name, safe='')
        payload = f"baikeid={baikeid}&name={encoded_name}&profile={STATIC_PROFILE}"
        resp = session.post(url_equity, data=payload.encode('utf-8'), headers=headers, timeout=10)
        if resp.status_code == 200:
            json_data = resp.json()
            if json_data.get('errno') == 0:
                data = json_data.get('data', {})
                head = data.get('head', {})
                result['total_gift'] = head.get('totalGift', 0)
            else:
                result['status'] += f" | 累计接口错误: {json_data.get('msg', '未知')}"
        else:
            result['status'] += f" | 累计HTTP {resp.status_code}"
    except Exception as e:
        result['status'] += f" | 累计异常: {str(e)}"

    return result

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {"timestamps": [], "series": {}}

def save_history(history):
    os.makedirs("docs", exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def update_history(current_data_list):
    history = load_history()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history["timestamps"].append(now_str)
    max_points = 48
    if len(history["timestamps"]) > max_points:
        history["timestamps"] = history["timestamps"][-max_points:]
        for name in history["series"]:
            if len(history["series"][name]["today_gift"]) > max_points:
                history["series"][name]["today_gift"] = history["series"][name]["today_gift"][-max_points:]
            if len(history["series"][name]["total_gift"]) > max_points:
                history["series"][name]["total_gift"] = history["series"][name]["total_gift"][-max_points:]

    for item in current_data_list:
        name = item["name"]
        if name not in history["series"]:
            history["series"][name] = {"today_gift": [], "total_gift": []}
        history["series"][name]["today_gift"].append(item["today_gift"])
        history["series"][name]["total_gift"].append(item["total_gift"])
        if len(history["series"][name]["today_gift"]) > max_points:
            history["series"][name]["today_gift"] = history["series"][name]["today_gift"][-max_points:]
        if len(history["series"][name]["total_gift"]) > max_points:
            history["series"][name]["total_gift"] = history["series"][name]["total_gift"][-max_points:]

    save_history(history)

def main():
    tasks = []
    if not os.path.exists(INPUT_FILE):
        print(f"错误: 找不到 {INPUT_FILE}")
        return
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ',' not in line:
                continue
            bid, name = line.split(',', 1)
            tasks.append((bid.strip(), name.strip()))

    print(f"共加载 {len(tasks)} 个任务")
    results = []
    for idx, (bid, name) in enumerate(tasks, 1):
        print(f"[{idx}/{len(tasks)}] 抓取: {name}")
        results.append(fetch_data(bid, name))
        time.sleep(random.uniform(1.5, 3))

    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    update_history(results)
    print("已更新 docs/data.json 和 docs/history.json")

if __name__ == "__main__":
    main()
