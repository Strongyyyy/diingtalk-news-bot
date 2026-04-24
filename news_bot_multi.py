import os
import requests
import json
from datetime import datetime
import time
import hmac
import hashlib
import base64
import urllib.parse

# ------------------------------
# 配置部分
# ------------------------------
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")  # GitHub Secrets 里配置
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")    # 钉钉机器人加签，若未启用加签可留空
NEWS_API_KEY = os.getenv("NEWS_API_KEY")          # 聚合数据 API Key

# 新闻来源配置
NEWS_SOURCES = [
    {
        "name": "聚合数据头条",
        "url": "http://v.juhe.cn/toutiao/index",
        "params": lambda: {"key": NEWS_API_KEY, "type": "top"}
    },
    # 可以添加更多来源
]

CACHE_FILE = "sent_news.txt"

# ------------------------------
# 钉钉加签处理
# ------------------------------
def get_signed_webhook(webhook, secret):
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"{webhook}&timestamp={timestamp}&sign={sign}"

# ------------------------------
# 获取新闻
# ------------------------------
def get_news_from_source(source):
    try:
        response = requests.get(source["url"], params=source["params"](), timeout=10)
        data = response.json()
        if data.get('error_code') != 0:
            print(f"[{source['name']}] 获取新闻失败: {data.get('reason')}")
            return []
        news_list = data['result']['data'][:10]
        return [{"title": n["title"], "url": n["url"]} for n in news_list]
    except Exception as e:
        print(f"[{source['name']}] 异常: {e}")
        return []

def get_all_news():
    all_news = []
    for source in NEWS_SOURCES:
        news_items = get_news_from_source(source)
        all_news.extend(news_items)
    return all_news

# ------------------------------
# 去重处理
# ------------------------------
def load_sent_titles():
    if not os.path.exists(CACHE_FILE):
        return set()
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_sent_titles(titles):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        for title in titles:
            f.write(title + "\n")

def deduplicate_news(news_list, sent_titles):
    unique_news = [n for n in news_list if n["title"] not in sent_titles]
    return unique_news

# ------------------------------
# 推送到钉钉
# ------------------------------
def send_to_dingtalk(news_list):
    if not news_list:
        return "今日没有新新闻"
    message = f"### 今日新闻热点 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    for n in news_list:
        message += f"- [{n['title']}]({n['url']})\n"
    payload = {"msgtype": "markdown", "markdown": {"title": "每日新闻热点", "text": message}}
    headers = {"Content-Type": "application/json"}
    webhook = get_signed_webhook(DINGTALK_WEBHOOK, DINGTALK_SECRET)
    try:
        r = requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=5)
        return r.text
    except Exception as e:
        return f"发送钉钉异常: {e}"

# ------------------------------
# 主程序
# ------------------------------
if __name__ == "__main__":
    sent_titles = load_sent_titles()
    all_news = get_all_news()
    new_news = deduplicate_news(all_news, sent_titles)
    result = send_to_dingtalk(new_news)
    print("钉钉返回:", result)
    if new_news:
        updated_titles = sent_titles.union({n["title"] for n in new_news})
        save_sent_titles(updated_titles)
