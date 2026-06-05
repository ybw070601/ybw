import requests
import time
import random
import os
import json
import re
from urllib.parse import quote
from datetime import datetime, timedelta, timezone

# 设置北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

def beijing_now():
    """返回当前北京时间（带时区信息）"""
    return datetime.now(BEIJING_TZ)

# ==================== 配置区 ====================
INPUT_FILE = "input.txt"
HISTORY_FILE = "docs/history.json"
DATA_FILE = "docs/data.json"
COMPARE_FILE = "docs/compare_yangbowen.json"

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
    now_str = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    history["timestamps"].append(now_str)
    max_points = 48   # 保留最近48个点（24小时）
    if len(history["timestamps"]) > max_points:
        history["timestamps"] = history["timestamps"][-max_points:]
        for name in history["series"]:
            for key in ["today_gift", "today_users", "avg", "total_gift"]:
                if key in history["series"][name] and len(history["series"][name][key]) > max_points:
                    history["series"][name][key] = history["series"][name][key][-max_points:]

    for item in current_data_list:
        name = item["name"]
        if name not in history["series"]:
            history["series"][name] = {
                "today_gift": [],
                "today_users": [],
                "avg": [],
                "total_gift": []
            }
        # 确保每个键都存在
        for key in ["today_gift", "today_users", "avg", "total_gift"]:
            if key not in history["series"][name]:
                history["series"][name][key] = []
        history["series"][name]["today_gift"].append(item["today_gift"])
        history["series"][name]["today_users"].append(item["today_users"])
        history["series"][name]["avg"].append(item["avg"])
        history["series"][name]["total_gift"].append(item["total_gift"])
        # 保持长度
        for key in ["today_gift", "today_users", "avg", "total_gift"]:
            if len(history["series"][name][key]) > max_points:
                history["series"][name][key] = history["series"][name][key][-max_points:]

    save_history(history)

def generate_compare_data(current_data_list, history):
    """生成杨博文今天与昨天同一时刻的对比数据（基于北京时间）"""
    # 查找杨博文当前数据
    yang = None
    for item in current_data_list:
        if item["name"] == "杨博文":
            yang = item
            break
    if not yang:
        return None

    # 获取历史数据中的杨博文系列
    yang_history = history.get("series", {}).get("杨博文", {})
    timestamps = history.get("timestamps", [])
    if not timestamps or not yang_history.get("today_gift"):
        return None

    # 获取当前北京时间
    now = beijing_now()
    # 昨天同一时刻（精确到分钟）
    yesterday = now - timedelta(days=1)
    target_prefix = yesterday.strftime("%Y-%m-%d %H:%M")

    # 在 timestamps 中找到匹配的索引
    best_idx = None
    for idx, ts in enumerate(timestamps):
        if ts.startswith(target_prefix):
            best_idx = idx
            break
    # 如果没找到精确匹配，找时间差最小的点
    if best_idx is None:
        best_idx = min(range(len(timestamps)), key=lambda i: abs((datetime.strptime(timestamps[i], "%Y-%m-%d %H:%M:%S") - yesterday).total_seconds()))

    yesterday_data = {
        "timestamp": timestamps[best_idx],
        "today_gift": yang_history.get("today_gift", [])[best_idx] if best_idx < len(yang_history.get("today_gift", [])) else 0,
        "today_users": yang_history.get("today_users", [])[best_idx] if best_idx < len(yang_history.get("today_users", [])) else 0,
        "avg": yang_history.get("avg", [])[best_idx] if best_idx < len(yang_history.get("avg", [])) else 0
    }

    compare = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "today": {
            "today_gift": yang["today_gift"],
            "today_users": yang["today_users"],
            "avg": yang["avg"]
        },
        "yesterday": {
            "today_gift": yesterday_data["today_gift"],
            "today_users": yesterday_data["today_users"],
            "avg": yesterday_data["avg"]
        },
        "yesterday_timestamp": yesterday_data["timestamp"]
    }
    return compare

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
    # 保存最新快照
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 更新历史并生成对比
    update_history(results)
    # 重新加载历史
    history = load_history()
    compare_data = generate_compare_data(results, history)
    if compare_data:
        with open(COMPARE_FILE, 'w', encoding='utf-8') as f:
            json.dump(compare_data, f, ensure_ascii=False, indent=2)
        print("已生成杨博文对比数据")
    else:
        print("未能生成对比数据")

    print("已更新 docs/data.json, docs/history.json, docs/compare_yangbowen.json")

if __name__ == "__main__":
    main()
