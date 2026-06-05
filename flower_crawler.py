import requests
import time
import random
import os
import re
from urllib.parse import quote

INPUT_FILE = "input.txt"
OUTPUT_HTML = "docs/index.html"

STATIC_PROFILE = "aHR0cHM6Ly9ia2ltZy5jZG4uYmNlYm9zLmNvbS9zbWFydC80YjkwZjYwMzczOGRhOTc3MzkxMjhiMTkwNjBkZWYxOTg2MTgzNjdhNDVmNi1ia2ltZy1wcm9jZXNzLHZfMSxyd18xLHJoXzEsbWF4bF84MDAscGFkXzE%2FeC1iY2UtcHJvY2Vzcz1pbWFnZSUyRmZvcm1hdCUyQ2ZfYXV0byUyRnJlc2l6ZSUyQ21fZmlsbCUyQ3dfMTAwJTJDaF8xMDA%3D"

def clean_cookie(c):
    return re.sub(r'[^\x20-\x7E]+', '', c).strip()

RAW_COOKIE = os.environ.get("BAIDU_COOKIE", "")
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
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

def fetch_data(baikeid, name):
    result = {"name": name, "id": baikeid, "today_gift": 0, "today_users": 0, "avg": 0, "total_gift": 0, "status": "成功"}
    session = requests.Session()
    url_trend = "https://figure.baidu.com/api/land/interact/getTrend"
    url_equity = "https://figure.baidu.com/api/land/interact/getEquity"

    try:
        headers = build_headers(baikeid, name)
        r = session.post(url_trend, data=f"baikeid={baikeid}", headers=headers, timeout=10)
        if r.status_code == 200 and r.json().get('errno') == 0:
            d = r.json().get('data', {})
            result['today_gift'] = d.get('userGift', 0)
            result['today_users'] = d.get('userNum', 0)
            result['avg'] = round(result['today_gift'] / result['today_users'], 2) if result['today_users'] > 0 else 0
        else:
            result['status'] = "趋势接口失败"
    except Exception as e:
        result['status'] = f"趋势异常: {str(e)}"

    try:
        headers = build_headers(baikeid, name)
        encoded_name = quote(name, safe='')
        payload = f"baikeid={baikeid}&name={encoded_name}&profile={STATIC_PROFILE}"
        r = session.post(url_equity, data=payload.encode('utf-8'), headers=headers, timeout=10)
        if r.status_code == 200 and r.json().get('errno') == 0:
            data = r.json().get('data', {})
            result['total_gift'] = data.get('head', {}).get('totalGift', 0)
        else:
            result['status'] += " | 累计接口失败"
    except Exception as e:
        result['status'] += f" | 累计异常: {str(e)}"

    return result

def generate_json(data_list):
    import json
    return json.dumps(data_list, ensure_ascii=False, indent=2)

def main():
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
    results = []
    for bid, name in tasks:
        print(f"抓取: {name}")
        results.append(fetch_data(bid, name))
        time.sleep(random.uniform(1, 2))
    
    os.makedirs("docs", exist_ok=True)
    # 保存 JSON 数据
    with open("docs/data.json", "w", encoding="utf-8") as f:
        f.write(generate_json(results))
    # 保存 HTML（可选，也可以用上面的静态 HTML 作为模板）
    # 但建议保留静态 HTML，只更新 JSON
    print("已生成 docs/data.json")
