import requests
import time
import random
import os
import json
import re
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== 时区设置 ====================
BEIJING_TZ = timezone(timedelta(hours=8))
def beijing_now():
    return datetime.now(BEIJING_TZ)

def parse_beijing_time(ts_str):
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=BEIJING_TZ)

# ==================== 配置文件 ====================
BAIDU_INPUT_FILE = "input.txt"
XUNYI_MAPPING_FILE = "xunyi_mapping.txt"
BAIDU_INDEX_KEYWORDS_FILE = "baidu_index_keywords.txt"

HISTORY_FILE = "docs/history.json"
XUNYI_HISTORY_FILE = "docs/xunyi_history.json"
DATA_FILE = "docs/data.json"
COMPARE_FILE = "docs/compare_yangbowen.json"
XUNYI_COMPARE_FILE = "docs/compare_yangbowen_xunyi.json"
BAIDU_INDEX_TODAY_FILE = "docs/baidu_index_today.json"
BAIDU_INDEX_YANG_HISTORY_FILE = "docs/baidu_index_yang_history.json"

STATIC_PROFILE = "aHR0cHM6Ly9ia2ltZy5jZG4uYmNlYm9zLmNvbS9zbWFydC80YjkwZjYwMzczOGRhOTc3MzkxMjhiMTkwNjBkZWYxOTg2MTgzNjdhNDVmNi1ia2ltZy1wcm9jZXNzLHZfMSxyd18xLHJoXzEsbWF4bF84MDAscGFkXzE%2FeC1iY2UtcHJvY2Vzcz1pbWFnZSUyRmZvcm1hdCUyQ2ZfYXV0byUyRnJlc2l6ZSUyQ21fZmlsbCUyQ3dfMTAwJTJDaF8xMDA%3D"

RAW_COOKIE = os.environ.get("BAIDU_COOKIE", "")
if not RAW_COOKIE:
    print("警告: 未设置 BAIDU_COOKIE 环境变量")

def clean_cookie(c):
    return re.sub(r'[^\x20-\x7E]+', '', c).strip()
COOKIE_STRING = clean_cookie(RAW_COOKIE)

# 百度指数相关凭证
BAIDU_INDEX_COOKIE = os.environ.get("BAIDU_INDEX_COOKIE", "")
BAIDU_INDEX_CIPHER = os.environ.get("BAIDU_INDEX_CIPHER", "")
if not BAIDU_INDEX_COOKIE or not BAIDU_INDEX_CIPHER:
    print("警告: 未设置 BAIDU_INDEX_COOKIE 或 BAIDU_INDEX_CIPHER，百度指数将跳过")

# ==================== 读取数据 ====================
def load_baidu_tasks():
    tasks = []
    if not os.path.exists(BAIDU_INPUT_FILE):
        return []
    with open(BAIDU_INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ',' not in line:
                continue
            bid, name = line.split(',', 1)
            tasks.append((bid.strip(), name.strip()))
    return tasks

def load_xunyi_mapping():
    mapping = {}
    if not os.path.exists(XUNYI_MAPPING_FILE):
        return {}
    with open(XUNYI_MAPPING_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ',' not in line:
                continue
            name, pid = line.split(',', 1)
            mapping[name.strip()] = int(pid.strip())
    return mapping

def load_baidu_index_keywords():
    keywords = []
    if not os.path.exists(BAIDU_INDEX_KEYWORDS_FILE):
        print(f"警告: 找不到 {BAIDU_INDEX_KEYWORDS_FILE}")
        return []
    with open(BAIDU_INDEX_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                keywords.append(line)
    return keywords

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
    result = {"name": name, "id": baikeid, "today_gift": 0, "today_users": 0, "avg": 0, "total_gift": 0, "status": "成功"}
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
                result['status'] = "趋势错误"
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
def fetch_xunyi_data(name, pid):
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
                return {
                    "name": name, "check1": check1, "check2": check2, "check3": check3,
                    "total_points": total_points, "percent1": pct1, "percent2": pct2, "percent3": pct3,
                    "status": "成功"
                }
            else:
                return {"name": name, "status": "接口返回错误"}
        else:
            return {"name": name, "status": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"name": name, "status": f"异常: {str(e)}"}

# ==================== 历史记录管理（通用） ====================
def load_history(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default

def save_history(file_path, history):
    os.makedirs("docs", exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def update_history_general(file_path, current_data_dict, max_points=144):
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

# ==================== 杨博文对比 ====================
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
    return {"update_time": now.strftime("%Y-%m-%d %H:%M:%S"), "today": yang, "yesterday": yesterday_data}

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
    yesterday_data = {"timestamp": timestamps[best_idx], "total_points": safe_get(yang_hist.get("total_points", []), best_idx)}
    return {"update_time": now.strftime("%Y-%m-%d %H:%M:%S"), "today": {"total_points": yang["total_points"]}, "yesterday": yesterday_data}

# ==================== 百度指数接口 ====================
def decrypt(ptbk, encrypted_data):
    if not ptbk:
        return ""
    n = len(ptbk) // 2
    d = {ptbk[o]: ptbk[n + o] for o in range(n)}
    decrypted_data = [d[data] for data in encrypted_data]
    return ''.join(decrypted_data)

def fetch_baidu_index_for_keyword(keyword, start_date, end_date, retry=2):
    if not BAIDU_INDEX_COOKIE or not BAIDU_INDEX_CIPHER:
        return None
    url = "https://index.baidu.com/api/SearchApi/index"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "cipher-text": BAIDU_INDEX_CIPHER,
        "Connection": "keep-alive",
        "Cookie": BAIDU_INDEX_COOKIE,
        "Host": "index.baidu.com",
        "Pragma": "no-cache",
        "Referer": "https://index.baidu.com/v2/main/index.html",
        "sec-ch-ua": '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
    }
    params = {
        "area": "0",
        "word": json.dumps([[{"name": keyword, "wordType": 1}]]),
        "startDate": start_date,
        "endDate": end_date
    }
    for attempt in range(retry):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"百度指数请求失败 {keyword}: HTTP {resp.status_code}")
                if attempt < retry-1:
                    time.sleep(2)
                    continue
                return None
            data = resp.json()
            if data.get("status") != 0 or "data" not in data:
                print(f"百度指数返回错误 {keyword}: {data.get('msg')}")
                if attempt < retry-1:
                    time.sleep(2)
                    continue
                return None
            encrypted_data = data["data"]
            uniqid = encrypted_data.get("uniqid")
            if not uniqid:
                print(f"百度指数无 uniqid {keyword}")
                return None
            ptbk_url = f"http://index.baidu.com/Interface/ptbk?uniqid={uniqid}"
            ptbk_resp = requests.get(ptbk_url, headers=headers, timeout=10)
            if ptbk_resp.status_code != 200:
                print(f"获取ptbk失败 {keyword}")
                return None
            ptbk = ptbk_resp.json().get("data", "")
            if not ptbk:
                print(f"ptbk为空 {keyword}")
                return None
            user_indexes = encrypted_data.get("userIndexes", [])
            if not user_indexes:
                print(f"userIndexes为空 {keyword}")
                return None
            item = user_indexes[0]
            all_enc = item["all"]["data"]
            all_str = decrypt(ptbk, all_enc)
            if not all_str:
                print(f"解密失败 {keyword}")
                return None
            all_vals = [int(v) if v else 0 for v in all_str.split(",")]
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]
            return {"dates": dates, "all": all_vals}
        except Exception as e:
            print(f"百度指数抓取异常 {keyword} (尝试 {attempt+1}/{retry}): {str(e)}")
            if attempt < retry-1:
                time.sleep(2)
            else:
                return None
    return None

def fetch_baidu_index_today_concurrent(keywords):
    today_str = beijing_now().strftime("%Y-%m-%d")
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_kw = {executor.submit(fetch_baidu_index_for_keyword, kw, today_str, today_str): kw for kw in keywords}
        for future in as_completed(future_to_kw):
            kw = future_to_kw[future]
            try:
                data = future.result()
                if data and data["all"]:
                    score = data["all"][0]
                    results.append({"name": kw, "score": score, "date": today_str, "status": "成功"})
                else:
                    print(f"[百度指数] {kw} 抓取失败")
                    results.append({"name": kw, "score": 0, "date": today_str, "status": "抓取失败"})
            except Exception as e:
                print(f"[百度指数] {kw} 异常: {e}")
                results.append({"name": kw, "score": 0, "date": today_str, "status": "异常"})
    return results

def fetch_baidu_index_yang_history():
    keyword = "杨博文"
    end_date = beijing_now().strftime("%Y-%m-%d")
    start_date = (beijing_now() - timedelta(days=14)).strftime("%Y-%m-%d")
    print(f"[百度指数] 抓取杨博文历史数据 {start_date} 至 {end_date}")
    data = fetch_baidu_index_for_keyword(keyword, start_date, end_date)
    if data:
        return [{"date": d, "score": v} for d, v in zip(data["dates"], data["all"])]
    else:
        return []

# ==================== 并发抓取函数 ====================
def fetch_all_baidu_data_concurrent(tasks):
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(fetch_baidu_data, bid, name): (bid, name) for bid, name in tasks}
        for future in as_completed(future_to_task):
            bid, name = future_to_task[future]
            try:
                result = future.result()
                results.append(result)
                print(f"[百度] {name} 完成")
            except Exception as e:
                print(f"[百度] {name} 异常: {e}")
                results.append({"name": name, "id": bid, "today_gift": 0, "today_users": 0, "avg": 0, "total_gift": 0, "status": "异常"})
    return results

def fetch_all_xunyi_data_concurrent(mapping):
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_name = {executor.submit(fetch_xunyi_data, name, pid): name for name, pid in mapping.items()}
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                result = future.result()
                results.append(result)
                print(f"[寻艺] {name} 完成")
            except Exception as e:
                print(f"[寻艺] {name} 异常: {e}")
                results.append({"name": name, "status": "异常"})
    return results

# ==================== main ====================
def main():
    start_time = time.time()
    
    # 1. 百度送花（并发）
    baidu_tasks = load_baidu_tasks()
    if baidu_tasks:
        print(f"百度送花 {len(baidu_tasks)} 个，开始并发抓取...")
        baidu_results = fetch_all_baidu_data_concurrent(baidu_tasks)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(baidu_results, f, ensure_ascii=False, indent=2)
        baidu_series = {item["name"]: {"today_gift": item["today_gift"], "today_users": item["today_users"], "avg": item["avg"], "total_gift": item["total_gift"]} for item in baidu_results}
        update_history_general(HISTORY_FILE, baidu_series, max_points=144)
        baidu_history = load_history(HISTORY_FILE, {"timestamps": [], "series": {}})
        baidu_compare = generate_baidu_compare(baidu_results, baidu_history)
        if baidu_compare:
            with open(COMPARE_FILE, 'w', encoding='utf-8') as f:
                json.dump(baidu_compare, f, ensure_ascii=False, indent=2)

    # 2. 寻艺（并发）
    xunyi_mapping = load_xunyi_mapping()
    if xunyi_mapping:
        print(f"寻艺 {len(xunyi_mapping)} 个，开始并发抓取...")
        xunyi_results = fetch_all_xunyi_data_concurrent(xunyi_mapping)
        xunyi_series = {}
        for item in xunyi_results:
            if "total_points" in item:
                xunyi_series[item["name"]] = {k: item[k] for k in ["total_points", "check1", "check2", "check3", "percent1", "percent2", "percent3"] if k in item}
        if xunyi_series:
            update_history_general(XUNYI_HISTORY_FILE, xunyi_series, max_points=144)
            xunyi_history = load_history(XUNYI_HISTORY_FILE, {"timestamps": [], "series": {}})
            xunyi_compare = generate_xunyi_compare(xunyi_results, xunyi_history)
            if xunyi_compare:
                with open(XUNYI_COMPARE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(xunyi_compare, f, ensure_ascii=False, indent=2)

    # 3. 百度指数
    if BAIDU_INDEX_COOKIE and BAIDU_INDEX_CIPHER:
        keywords = load_baidu_index_keywords()
        if keywords:
            print(f"百度指数当日 {len(keywords)} 个，开始并发抓取...")
            today_data = fetch_baidu_index_today_concurrent(keywords)
            if today_data:
                with open(BAIDU_INDEX_TODAY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(today_data, f, ensure_ascii=False, indent=2)
                print("百度指数当日数据已更新")
            yang_history = fetch_baidu_index_yang_history()
            if yang_history:
                with open(BAIDU_INDEX_YANG_HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(yang_history, f, ensure_ascii=False, indent=2)
                print("百度指数杨博文历史数据已更新")
        else:
            print("百度指数关键词列表为空")
    else:
        print("百度指数凭证缺失，跳过")

    elapsed = time.time() - start_time
    print(f"所有数据更新完成，总耗时: {elapsed:.2f} 秒")

if __name__ == "__main__":
    main()
