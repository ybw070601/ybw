import requests
import time
import random
import os
import json
import re
from urllib.parse import quote
from datetime import datetime, timedelta, timezone

# ==================== 时区设置 ====================
BEIJING_TZ = timezone(timedelta(hours=8))
def beijing_now():
    return datetime.now(BEIJING_TZ)

def parse_beijing_time(ts_str):
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=BEIJING_TZ)

# ==================== 配置 ====================
INPUT_FILE = "input.txt"
HISTORY_FILE = "docs/history.json"                # 百度送花历史
XUNYI_HISTORY_FILE = "docs/xunyi_history.json"    # 寻艺历史
DATA_FILE = "docs/data.json"                      # 百度最新快照
COMPARE_FILE = "docs/compare_yangbowen.json"      # 百度对比
XUNYI_COMPARE_FILE = "docs/compare_yangbowen_xunyi.json"  # 寻艺杨博文对比

STATIC_PROFILE = "aHR0cHM6Ly9ia2ltZy5jZG4uYmNlYm9zLmNvbS9zbWFydC80YjkwZjYwMzczOGRhOTc3MzkxMjhiMTkwNjBkZWYxOTg2MTgzNjdhNDVmNi1ia2ltZy1wcm9jZXNzLHZfMSxyd18xLHJoXzEsbWF4bF84MDAscGFkXzE%2FeC1iY2UtcHJvY2Vzcz1pbWFnZSUyRmZvcm1hdCUyQ2ZfYXV0byUyRnJlc2l6ZSUyQ21fZmlsbCUyQ3dfMTAwJTJDaF8xMDA%3D"

RAW_COOKIE = os.environ.get("BAIDU_COOKIE", "")
if not RAW_COOKIE:
    print("警告: 未设置 BAIDU_COOKIE 环境变量，请确保在 GitHub Secrets 中配置。")

def clean_cookie(c):
    return re.sub(r'[^\x20-\x7E]+', '', c).strip()
COOKIE_STRING = clean_cookie(RAW_COOKIE)

# ==================== 百度送花接口 ====================
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

def fetch_baidu_data(baikeid, name):
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

    try:
        headers = build_headers(baikeid, name)
        resp = session.post(url_trend, data=f"baikeid={baikeid}", headers=headers, timeout=10)
        if resp.status_code == 200:
            json_data = resp.json()
            if json_data.get('errno') == 0:
                d = json_data.get('data', {})
                result['today_gift'] = d.get('userGift', 0)
                result['today_users'] = d.get('userNum', 0)
                result['avg'] = round(result['today_gift'] / result['today_users'], 2) if result['today_users'] > 0 else 0
            else:
                result['status'] = f"趋势错误"
        else:
            result['status'] = f"HTTP {resp.status_code}"
    except Exception as e:
        result['status'] = f"异常: {str(e)}"

    try:
        headers = build_headers(baikeid, name)
        payload = f"baikeid={baikeid}&name={quote(name, safe='')}&profile={STATIC_PROFILE}"
        resp = session.post(url_equity, data=payload.encode('utf-8'), headers=headers, timeout=10)
        if resp.status_code == 200:
            json_data = resp.json()
            if json_data.get('errno') == 0:
                data = json_data.get('data', {})
                head = data.get('head', {})
                result['total_gift'] = head.get('totalGift', 0)
            else:
                result['status'] += " | 累计接口错误"
        else:
            result['status'] += f" | HTTP {resp.status_code}"
    except Exception as e:
        result['status'] += f" | 累计异常: {str(e)}"

    return result

# ==================== 寻艺接口 ====================
XUNYI_MAP = {
    "张桂源": 198330,
    "张函瑞": 198334,
    "王橹杰": 198331,
    "左奇函": 198333,
    "陈奕恒": 198335,
    "杨博文": 198332,
    "陈浚明": 198336
}

def fetch_xunyi_data():
    results = []
    for name, pid in XUNYI_MAP.items():
        url = f"https://api.xunyee.cn/xunyee/vcuser_person/fans_check?person={pid}"
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541a1b) XWEB/19895',
                'Authorization': 'Bearer'
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 0 and data.get('data'):
                    d = data['data']
                    check1 = int(d.get('check1', 0))
                    check2 = int(d.get('check2', 0))
                    check3 = int(d.get('check3', 0))
                    total = check1 + check2 + check3
                    total_points = check1 * 1 + check2 * 2 + check3 * 3
                    pct1 = round(check1 / total * 100, 2) if total > 0 else 0
                    pct2 = round(check2 / total * 100, 2) if total > 0 else 0
                    pct3 = round(check3 / total * 100, 2) if total > 0 else 0
                    results.append({
                        "name": name,
                        "check1": check1,
                        "check2": check2,
                        "check3": check3,
                        "total_points": total_points,
                        "percent1": pct1,
                        "percent2": pct2,
                        "percent3": pct3,
                        "status": "成功"
                    })
                else:
                    results.append({"name": name, "status": "接口返回错误"})
            else:
                results.append({"name": name, "status": f"HTTP {resp.status_code}"})
        except Exception as e:
            results.append({"name": name, "status": f"异常: {str(e)}"})
    return results

# ==================== 历史记录管理（通用） ====================
def load_history(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return default

def save_history(file_path, history):
    os.makedirs("docs", exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def update_history_general(file_path, series_key, current_data_dict, max_points=144):
    history = load_history(file_path, {"timestamps": [], "series": {}})
    now_str = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    history["timestamps"].append(now_str)
    if len(history["timestamps"]) > max_points:
        history["timestamps"] = history["timestamps"][-max_points:]
        for name in history["series"]:
            for key in history["series"][name]:
                if len(history["series"][name][key]) > max_points:
                    history["series"][name][key] = history["series"][name][key][-max_points:]

    for name, value in current_data_dict.items():
        if name not in history["series"]:
            history["series"][name] = {}
        for k, v in value.items():
            if k not in history["series"][name]:
                history["series"][name][k] = []
            history["series"][name][k].append(v)
            if len(history["series"][name][k]) > max_points:
                history["series"][name][k] = history["series"][name][k][-max_points:]

    save_history(file_path, history)
    return history

# ==================== 杨博文对比（百度） ====================
def generate_baidu_compare(current_data_list, history):
    yang = next((item for item in current_data_list if item["name"] == "杨博文"), None)
    if not yang: return None
    timestamps = history.get("timestamps", [])
    yang_hist = history.get("series", {}).get("杨博文", {})
    if not timestamps or not yang_hist.get("today_gift"): return None
    now = beijing_now()
    yesterday = now - timedelta(days=1)
    target_prefix = yesterday.strftime("%Y-%m-%d %H:%M")
    best_idx = None
    for idx, ts in enumerate(timestamps):
        if ts.startswith(target_prefix):
            best_idx = idx
            break
    if best_idx is None:
        parsed = [parse_beijing_time(ts) for ts in timestamps]
        best_idx = min(range(len(timestamps)), key=lambda i: abs((parsed[i] - yesterday).total_seconds()))
    def safe_get(lst, idx):
        return lst[idx] if idx < len(lst) else 0
    yesterday_data = {
        "timestamp": timestamps[best_idx],
        "today_gift": safe_get(yang_hist.get("today_gift", []), best_idx),
        "today_users": safe_get(yang_hist.get("today_users", []), best_idx),
        "avg": safe_get(yang_hist.get("avg", []), best_idx),
    }
    return {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "today": yang,
        "yesterday": yesterday_data
    }

# ==================== 杨博文对比（寻艺） ====================
def generate_xunyi_compare(current_list, history):
    yang = next((item for item in current_list if item["name"] == "杨博文"), None)
    if not yang: return None
    timestamps = history.get("timestamps", [])
    yang_hist = history.get("series", {}).get("杨博文", {})
    if not timestamps or not yang_hist.get("total_points"): return None
    now = beijing_now()
    yesterday = now - timedelta(days=1)
    target_prefix = yesterday.strftime("%Y-%m-%d %H:%M")
    best_idx = None
    for idx, ts in enumerate(timestamps):
        if ts.startswith(target_prefix):
            best_idx = idx
            break
    if best_idx is None:
        parsed = [parse_beijing_time(ts) for ts in timestamps]
        best_idx = min(range(len(timestamps)), key=lambda i: abs((parsed[i] - yesterday).total_seconds()))
    def safe_get(lst, idx):
        return lst[idx] if idx < len(lst) else 0
    yesterday_data = {
        "timestamp": timestamps[best_idx],
        "total_points": safe_get(yang_hist.get("total_points", []), best_idx),
    }
    return {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "today": {"total_points": yang["total_points"]},
        "yesterday": yesterday_data
    }

# ==================== main ====================
def main():
    # 读取input.txt
    tasks = []
    if not os.path.exists(INPUT_FILE):
        print("错误: 找不到 input.txt")
        return
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ',' not in line: continue
            bid, name = line.split(',', 1)
            tasks.append((bid.strip(), name.strip()))
    print(f"共 {len(tasks)} 个任务")

    # 百度送花数据
    baidu_results = []
    for bid, name in tasks:
        print(f"[百度] 抓取: {name}")
        baidu_results.append(fetch_baidu_data(bid, name))
        time.sleep(random.uniform(1, 2))

    # 寻艺数据
    xunyi_results = fetch_xunyi_data()
    for item in xunyi_results:
        print(f"[寻艺] {item['name']} 总获赞: {item.get('total_points',0)}")

    # 保存百度最新快照
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(baidu_results, f, ensure_ascii=False, indent=2)

    # 更新百度历史
    baidu_series = {}
    for item in baidu_results:
        baidu_series[item["name"]] = {
            "today_gift": item["today_gift"],
            "today_users": item["today_users"],
            "avg": item["avg"],
            "total_gift": item["total_gift"]
        }
    update_history_general(HISTORY_FILE, "series", baidu_series, max_points=144)

    # 更新寻艺历史
    xunyi_series = {}
    for item in xunyi_results:
        xunyi_series[item["name"]] = {
            "total_points": item.get("total_points", 0),
            "check1": item.get("check1", 0),
            "check2": item.get("check2", 0),
            "check3": item.get("check3", 0),
            "percent1": item.get("percent1", 0),
            "percent2": item.get("percent2", 0),
            "percent3": item.get("percent3", 0)
        }
    update_history_general(XUNYI_HISTORY_FILE, "series", xunyi_series, max_points=144)

    # 杨博文对比（百度）
    baidu_history = load_history(HISTORY_FILE, {"timestamps": [], "series": {}})
    baidu_compare = generate_baidu_compare(baidu_results, baidu_history)
    if baidu_compare:
        with open(COMPARE_FILE, 'w', encoding='utf-8') as f:
            json.dump(baidu_compare, f, ensure_ascii=False, indent=2)

    # 杨博文对比（寻艺）
    xunyi_history = load_history(XUNYI_HISTORY_FILE, {"timestamps": [], "series": {}})
    xunyi_compare = generate_xunyi_compare(xunyi_results, xunyi_history)
    if xunyi_compare:
        with open(XUNYI_COMPARE_FILE, 'w', encoding='utf-8') as f:
            json.dump(xunyi_compare, f, ensure_ascii=False, indent=2)

    print("所有数据更新完成")

if __name__ == "__main__":
    main()
