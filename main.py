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
BAIDU_INDEX_KEYWORDS_FILE = "baidu_index_keywords.txt"

# --- 新增：微博相关文件 ---
WEIBO_UID_FILE = "weibouid.txt"
WEIBO_DAILY_SNAPSHOT_FILE = "docs/weibo_daily_snapshot.json"
WEIBO_TODAY_FILE = "docs/weibo_today.json"
WEIBO_CUMULATIVE_FILE = "docs/weibo_cumulative.json"

# ... (百度送花、寻艺、百度指数等模块的配置保持不变) ...
# 为节约篇幅，原配置区、函数`load_baidu_tasks`, `load_xunyi_mapping`, `load_baidu_index_keywords`等保持不变。
# 请确保你的 main.py 中包含了你之前已有的所有配置和函数。

# ... (新增函数: load_weibo_uids, fetch_weibo_data, init_weibo_daily_snapshot, save_weibo_data 等) ...

# ==================== 微博模块 ====================
def load_weibo_uids():
    """从 weibouid.txt 读取 uid 和名字"""
    uids = {}
    if not os.path.exists(WEIBO_UID_FILE):
        print(f"警告: 找不到 {WEIBO_UID_FILE}")
        return uids
    with open(WEIBO_UID_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) == 2:
                uid, name = parts
                uids[uid.strip()] = name.strip()
    return uids

def fetch_weibo_data(uid):
    """抓取单个用户的微博实时数据"""
    url = f"https://weibo.com/ajax/profile/info?uid={uid}&scene=profile"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://weibo.com/u/{uid}",
        "Cookie": "YOUR_WEIBO_COOKIE_HERE",  # ⚠️ 必须替换为你自己的微博Cookie
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # 提取所需字段，缺失则默认为0
            return {
                "comment_cnt": int(data.get('comment_cnt', 0)),
                "repost_cnt": int(data.get('repost_cnt', 0)),
                "like_cnt": int(data.get('like_cnt', 0)),
                "total_cnt": int(data.get('total_cnt', 0)),
                "followers_count": int(data.get('followers_count', 0))
            }
        else:
            print(f"微博数据抓取失败 {uid}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"微博数据抓取异常 {uid}: {str(e)}")
    return None

def init_weibo_daily_snapshot(weibo_uids):
    """初始化或更新当天的0点快照"""
    snapshot = {}
    if os.path.exists(WEIBO_DAILY_SNAPSHOT_FILE):
        with open(WEIBO_DAILY_SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
    today_str = beijing_now().strftime("%Y-%m-%d")
    # 如果快照不是今天的，就重新抓取
    if snapshot.get("date") != today_str:
        print("当天0点快照不存在或已过期，开始抓取...")
        current_data = {}
        for uid, name in weibo_uids.items():
            print(f"[微博0点快照] 抓取 {name} 数据...")
            data = fetch_weibo_data(uid)
            if data:
                current_data[name] = data
            else:
                current_data[name] = {"comment_cnt":0, "repost_cnt":0, "like_cnt":0, "total_cnt":0, "followers_count":0}
            time.sleep(random.uniform(1, 2))
        snapshot = {"date": today_str, "data": current_data}
        with open(WEIBO_DAILY_SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print("当天0点快照已更新")
    return snapshot

def save_weibo_data(weibo_uids, daily_snapshot):
    """保存今日增量数据和累计数据"""
    current_data = {}
    for uid, name in weibo_uids.items():
        print(f"[微博实时] 抓取 {name} 数据...")
        data = fetch_weibo_data(uid)
        if data:
            current_data[name] = data
        else:
            current_data[name] = {"comment_cnt":0, "repost_cnt":0, "like_cnt":0, "total_cnt":0, "followers_count":0}
        time.sleep(random.uniform(1, 2))

    # 计算增量
    snapshot_data = daily_snapshot.get("data", {})
    today_data = []
    cumulative_data = []
    for name, curr in current_data.items():
        base = snapshot_data.get(name, {"comment_cnt":0, "repost_cnt":0, "like_cnt":0, "total_cnt":0})
        today_data.append({
            "name": name,
            "comment_inc": curr["comment_cnt"] - base["comment_cnt"],
            "repost_inc": curr["repost_cnt"] - base["repost_cnt"],
            "like_inc": curr["like_cnt"] - base["like_cnt"],
            "total_inc": curr["total_cnt"] - base["total_cnt"]
        })
        cumulative_data.append({
            "name": name,
            "followers_count": curr["followers_count"],
            "comment": curr["comment_cnt"],
            "repost": curr["repost_cnt"],
            "like": curr["like_cnt"],
            "total": curr["total_cnt"]
        })
    
    with open(WEIBO_TODAY_FILE, 'w', encoding='utf-8') as f:
        json.dump(today_data, f, ensure_ascii=False, indent=2)
    with open(WEIBO_CUMULATIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cumulative_data, f, ensure_ascii=False, indent=2)
    print("微博数据已保存")

# ==================== main 函数 ====================
def main():
    # ... (原有的百度送花、寻艺、百度指数抓取代码保持不变) ...
    
    # --- 新增：微博数据抓取 ---
    weibo_uids = load_weibo_uids()
    if weibo_uids:
        print(f"共加载 {len(weibo_uids)} 个微博用户")
        # 确保当天0点快照存在
        daily_snapshot = init_weibo_daily_snapshot(weibo_uids)
        # 获取当前数据并保存
        save_weibo_data(weibo_uids, daily_snapshot)
    else:
        print("未找到微博用户数据，跳过")

    print("所有数据更新完成")

if __name__ == "__main__":
    main()
