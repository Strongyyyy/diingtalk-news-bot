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
# 配置
# ------------------------------
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")  # 未启用加签留空
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
CACHE_FILE = "sent_news.txt"

# 多来源示例
NEWS_SOURCES = [
    {
        "name": "聚合数据头条",
        "url": "http://v.juhe.cn/toutiao/index",
        "params": lambda: {"key": NEWS_API_KEY, "type": "top"}
    },
    # 可以加更多来源，例如：
    # {
    #     "name": "今日头条示例",
    #     "url": "https://api.example.com/news",
    #     "params": lambda: {"apikey": NEWS_API_KEY}
    # }
]

# ------------------------------
# 钉钉加签
# ------------------------------
def get_signed_webhook(webhook, secret):
    if not secret:
        return webhook
    try:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{secret}'
        hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{webhook}&timestamp={timestamp}&sign={sign}"
    except Exception as e:
        print("生成加签失败:", e)
        return webhook

# ------------------------------
# 新闻获取
# ------------------------------
def get_news_from_source(source):
    print(f"\n===== 获取新闻来源: {source['name']} =====")
    if not NEWS_API_KEY:
        print(f"[{source['name']}] NEWS_API_KEY 未设置")
        return []
    try:
        r = requests.get(source["url"], params=source["params"](), timeout=10)
        data = r.json()
        print(f"[{source['name']}] 接口返回: {json.dumps(data, ensure_ascii=False)[:500]}...")
        if data.get('error_code') != 0:
            print(f"[{source['name']}] 获取新闻失败: {data.get('reason')}")
            return []
        news_list = data['result']['data'][:10]
        return [{"title": n["title"], "url": n["url"]} for n in news_list]
    except Exception as e:
        print(f"[{source['name']}] 获取新闻异常: {e}")
        return []

def get_all_news():
    all_news = []
    for source in NEWS_SOURCES:
        all_news.extend(get_news_from_source(source))
    return all_news

# ------------------------------
# 去重
# ------------------------------
def load_sent_titles():
    try:
        if not os.path.exists(CACHE_FILE):
            return set()
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    except Exception as e:
        print("加载缓存异常:", e)
        return set()

def save_sent_titles(titles):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for title in titles:
                f.write(title + "\n")
    except Exception as e:
        print("保存缓存异常:", e)

def deduplicate_news(news_list, sent_titles):
    return [n for n in news_list if n["title"] not in sent_titles]

# ------------------------------
# 推送钉钉
# ------------------------------
def send_to_dingtalk(news_list):
    try:
        if not DINGTALK_WEBHOOK:
            print("DINGTALK_WEBHOOK 未设置，跳过推送")
            return "Webhook 未设置"
        if not news_list:
            message = f"今日没有新新闻 ({datetime.now().strftime('%Y-%m-%d')})"
        else:
            message = f"### 今日新闻热点 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
            for n in news_list:
                message += f"- [{n['title']}]({n['url']})\n"

        payload = {"msgtype": "markdown", "markdown": {"title": "每日新闻热点", "text": message}}
        headers = {"Content-Type": "application/json"}
        webhook = get_signed_webhook(DINGTALK_WEBHOOK, DINGTALK_SECRET)
        r = requests.post(webhook, headers=headers, data=json.dumps(payload), timeout=5)
        print("钉钉 HTTP 状态码:", r.status_code)
        print("钉钉返回内容:", r.text)
        return r.text
    except Exception as e:
        print("发送钉钉异常:", e)
        return f"异常: {e}"

# ------------------------------
# 主程序
# ------------------------------
if __name__ == "__main__":
    print("===== 调试信息 =====")
    print("DINGTALK_WEBHOOK:", "存在" if DINGTALK_WEBHOOK else "未设置")
    print("DINGTALK_SECRET:", "存在" if DINGTALK_SECRET else "未设置")
    print("NEWS_API_KEY:", "存在" if NEWS_API_KEY else "未设置")

    try:
        sent_titles = load_sent_titles()
        all_news = get_all_news()
        new_news = deduplicate_news(all_news, sent_titles)
        print(f"\n本次获取新闻数量: {len(all_news)}, 去重后新增数量: {len(new_news)}")
        result = send_to_dingtalk(new_news)
        print("发送结果:", result)

        if new_news:
            save_sent_titles(sent_titles.union({n["title"] for n in new_news}))
    except Exception as e:
        print("主程序异常:", e)

    print("===== 脚本结束 =====")
