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

# ==================== 配置文件 ====================
BAIDU_INPUT_FILE = "input.txt"
XUNYI_MAPPING_FILE = "xunyi_mapping.txt"
WECHAT_KEYWORDS_FILE = "wechat_keywords.txt"

HISTORY_FILE = "docs/history.json"
XUNYI_HISTORY_FILE = "docs/xunyi_history.json"
DATA_FILE = "docs/data.json"
COMPARE_FILE = "docs/compare_yangbowen.json"
XUNYI_COMPARE_FILE = "docs/compare_yangbowen_xunyi.json"
WECHAT_DATA_FILE = "docs/wechat_index.json"
WECHAT_HISTORY_FILE = "docs/wechat_history.json"  # 新增：微信指数历史（存储杨博文三个系列）

STATIC_PROFILE = "aHR0cHM6Ly9ia2ltZy5jZG4uYmNlYm9zLmNvbS9zbWFydC80YjkwZjYwMzczOGRhOTc3MzkxMjhiMTkwNjBkZWYxOTg2MTgzNjdhNDVmNi1ia2ltZy1wcm9jZXNzLHZfMSxyd18xLHJoXzEsbWF4bF84MDAscGFkXzE%2FeC1iY2UtcHJvY2Vzcz1pbWFnZSUyRmZvcm1hdCUyQ2ZfYXV0byUyRnJlc2l6ZSUyQ21fZmlsbCUyQ3dfMTAwJTJDaF8xMDA%3D"

RAW_COOKIE = os.environ.get("BAIDU_COOKIE", "")
if not RAW_COOKIE:
    print("警告: 未设置 BAIDU_COOKIE 环境变量")

def clean_cookie(c):
    return re.sub(r'[^\x20-\x7E]+', '', c).strip()
COOKIE_STRING = clean_cookie(RAW_COOKIE)

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

def load_wechat_keywords():
    """读取微信指数关键词，分组返回"""
    if not os.path.exists(WECHAT_KEYWORDS_FILE):
        return []
    keywords = []
    with open(WECHAT_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
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
def fetch_xunyi_data(mapping):
    results = []
    for name, pid in mapping.items():
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
                        "name": name, "check1": check1, "check2": check2, "check3": check3,
                        "total_points": total_points, "percent1": pct1, "percent2": pct2, "percent3": pct3,
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
    # ==================== 微信指数模块 ====================
WECHAT_OPENID = "ov4ns0FADrRvqZarXIS-Aq0HPzrY"  # 固定 openid
WECHAT_SEARCH_KEY = os.environ.get("WECHAT_SEARCH_KEY", "")  # 从环境变量读取

def fetch_single_wechat(keyword):
    """获取单个关键词的微信指数"""
    if not WECHAT_SEARCH_KEY:
        print("未设置 WECHAT_SEARCH_KEY，跳过")
        return None
    url = "https://search.weixin.qq.com/cgi-bin/searchweb/wxindex/querywxindexgroup"
    params = {
        "openid": WECHAT_OPENID,
        "search_key": WECHAT_SEARCH_KEY,
        "timestamp": int(time.time() * 1000),
        "wxindex_query_list": keyword
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781",
        "Referer": "https://servicewechat.com/wxc026e7662ec26a3a/77/page-frame.html",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                for item in data["data"]:
                    if item.get("keyword") == keyword:
                        score = item.get("score", 0)
                        date = str(item.get("time", datetime.now().strftime("%Y%m%d")))
                        return {"keyword": keyword, "score": score, "date": date, "status": "成功"}
                return {"keyword": keyword, "score": 0, "date": "", "status": "未找到数据"}
            else:
                return {"keyword": keyword, "score": 0, "date": "", "status": f"接口错误: {data.get('msg')}"}
        else:
            return {"keyword": keyword, "score": 0, "date": "", "status": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"keyword": keyword, "score": 0, "date": "", "status": f"异常: {str(e)}"}

def fetch_all_wechat():
    """获取所有分组关键词的指数，并组织成表格数据"""
    keywords = load_wechat_keywords()
    if not keywords:
        print("wechat_keywords.txt 为空或不存在")
        return None
    
    # 分组：第一组7人，第二组7人，第三组7人
    # 按顺序解析
    # 假设文件顺序：前7个为第一组（单人），接着7个为第二组（角色），最后7个为第三组（我们的少年时代2）
    # 如果顺序不对，可以通过检测关键词特征来分组，但这里按固定顺序
    group1_names = keywords[:7]   # 单人名字
    group2_keywords = keywords[7:14]  # 角色
    group3_keywords = keywords[14:21] # 我们的少年时代2
    
    # 同时获取杨博文的三项用于历史
    yangwen_single = None
    yangwen_role = None
    yangwen_drama = None
    
    results = []
    # 第一组（单人）
    for kw in group1_names:
        data = fetch_single_wechat(kw)
        if data:
            results.append({"type": "single", "name": kw, "score": data["score"], "date": data["date"], "status": data["status"]})
            if kw == "杨博文":
                yangwen_single = data["score"]
    # 第二组（角色）
    for kw in group2_keywords:
        data = fetch_single_wechat(kw)
        if data:
            results.append({"type": "role", "name": kw, "score": data["score"], "date": data["date"], "status": data["status"]})
            if kw == "杨博文 周扬":
                yangwen_role = data["score"]
    # 第三组（我们的少年时代2）
    for kw in group3_keywords:
        data = fetch_single_wechat(kw)
        if data:
            results.append({"type": "drama", "name": kw, "score": data["score"], "date": data["date"], "status": data["status"]})
            if kw == "杨博文 我们的少年时代2":
                yangwen_drama = data["score"]
    
    # 构建表格所需的数据结构：按人分组
    # 假设名字对应关系：第一组顺序与第二、三组顺序对应
    # 第一组7人顺序：张桂源, 张函瑞, 王橹杰, 左奇函, 陈奕恒, 杨博文, 陈浚明
    single_names = group1_names
    role_names = group2_keywords
    drama_names = group3_keywords
    
    table_rows = []
    for i in range(len(single_names)):
        single_kw = single_names[i]
        role_kw = role_names[i]
        drama_kw = drama_names[i]
        single_score = next((item["score"] for item in results if item["type"]=="single" and item["name"]==single_kw), 0)
        role_score = next((item["score"] for item in results if item["type"]=="role" and item["name"]==role_kw), 0)
        drama_score = next((item["score"] for item in results if item["type"]=="drama" and item["name"]==drama_kw), 0)
        table_rows.append({
            "name": single_kw,
            "single_score": single_score,
            "role_score": role_score,
            "drama_score": drama_score,
            "date": next((item["date"] for item in results if item["type"]=="single" and item["name"]==single_kw), ""),
            "status": "成功"
        })
    
    # 记录杨博文三个值用于历史
    yangwen_data = {
        "single": yangwen_single if yangwen_single is not None else 0,
        "role": yangwen_role if yangwen_role is not None else 0,
        "drama": yangwen_drama if yangwen_drama is not None else 0
    }
    
    return {"table": table_rows, "yangwen": yangwen_data}

# 更新微信指数历史（存储杨博文三个指标）
def update_wechat_history(current_yangwen):
    history = load_history(WECHAT_HISTORY_FILE, {"timestamps": [], "series": {"single": [], "role": [], "drama": []}})
    now_str = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    history["timestamps"].append(now_str)
    max_points = 10  # 保留最近10天（每天一个点）
    if len(history["timestamps"]) > max_points:
        history["timestamps"] = history["timestamps"][-max_points:]
        for key in ["single", "role", "drama"]:
            if len(history["series"][key]) > max_points:
                history["series"][key] = history["series"][key][-max_points:]
    history["series"]["single"].append(current_yangwen["single"])
    history["series"]["role"].append(current_yangwen["role"])
    history["series"]["drama"].append(current_yangwen["drama"])
    save_history(WECHAT_HISTORY_FILE, history)

# ==================== main ====================
def main():
    # 百度送花
    baidu_tasks = load_baidu_tasks()
    if baidu_tasks:
        print(f"百度送花 {len(baidu_tasks)} 个")
        baidu_results = []
        for bid, name in baidu_tasks:
            print(f"[百度] {name}")
            baidu_results.append(fetch_baidu_data(bid, name))
            time.sleep(random.uniform(1, 2))
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(baidu_results, f, ensure_ascii=False, indent=2)
        baidu_series = {item["name"]: {"today_gift": item["today_gift"], "today_users": item["today_users"], "avg": item["avg"], "total_gift": item["total_gift"]} for item in baidu_results}
        update_history_general(HISTORY_FILE, baidu_series, max_points=144)
        baidu_history = load_history(HISTORY_FILE, {"timestamps": [], "series": {}})
        baidu_compare = generate_baidu_compare(baidu_results, baidu_history)
        if baidu_compare:
            with open(COMPARE_FILE, 'w', encoding='utf-8') as f:
                json.dump(baidu_compare, f, ensure_ascii=False, indent=2)

    # 寻艺
    xunyi_mapping = load_xunyi_mapping()
    if xunyi_mapping:
        print(f"寻艺 {len(xunyi_mapping)} 个")
        xunyi_results = fetch_xunyi_data(xunyi_mapping)
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

    # 微信指数
    if WECHAT_SEARCH_KEY:
        wechat_data = fetch_all_wechat()
        if wechat_data:
            with open(WECHAT_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(wechat_data["table"], f, ensure_ascii=False, indent=2)
            # 更新杨博文历史
            update_wechat_history(wechat_data["yangwen"])
            print("微信指数数据已更新")
        else:
            print("微信指数数据抓取失败")
    else:
        print("未设置 WECHAT_SEARCH_KEY，跳过微信指数")

    print("所有数据更新完成")

if __name__ == "__main__":
    main()
