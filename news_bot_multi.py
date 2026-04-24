#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import hmac
import json
import hashlib
import base64
import urllib.parse
from datetime import datetime
import requests

# ================== 配置 ==================
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")  # 聚合数据 AppKey
CACHE_FILE = "sent_news.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

# ------------------ 新闻来源配置 ------------------
NEWS_SOURCES = [
    {
        "name": "知乎热榜",
        "api_func": lambda: fetch_zhihu_hot()
    },
    {
        "name": "微博热搜",
        "api_func": lambda: fetch_weibo_hot()
    },
    {
        "name": "聚合数据新闻",
        "api_func": lambda: fetch_juhe_news()
    }
]

# ================== 新闻接口 ==================
def fetch_zhihu_hot(limit=8):
    try:
        resp = requests.get("https://api.72v2.com/zhihu_hot", headers=HEADERS, timeout=10)
        data = resp.json()
        if data.get("code") == 200:
            return [item.get("title", "") for item in data.get("data", [])[:limit]]
        else:
            return [f"⚠️ 知乎热榜接口获取失败: {data.get('msg', '未知错误')}"]
    except Exception as e:
        return [f"❌ 知乎热榜接口获取失败: {str(e)}"]

def fetch_weibo_hot(limit=8):
    try:
        resp = requests.get("https://api.72v2.com/weibo_hot", headers=HEADERS, timeout=10)
        data = resp.json()
        if data.get("code") == 200:
            return [item.get("title", "") for item in data.get("data", [])[:limit]]
        else:
            return [f"⚠️ 微博热搜接口获取失败: {data.get('msg', '未知错误')}"]
    except Exception as e:
        return [f"❌ 微博热搜接口获取失败: {str(e)}"]

def fetch_juhe_news(limit=8):
    if not NEWS_API_KEY:
        return ["❌ 聚合数据 AppKey 未设置"]
    try:
        url = "http://v.juhe.cn/toutiao/index"
        params = {"key": NEWS_API_KEY, "type": "top"}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()
        if data.get("error_code") != 0:
            return [f"⚠️ 聚合数据新闻接口获取失败: {data.get('reason', '未知错误')}"]
        return [item.get("title", "") for item in data.get("result", {}).get("data", [])[:limit]]
    except Exception as e:
        return [f"❌ 聚合数据新闻接口获取失败: {str(e)}"]

# ================== 格式化 ==================
def format_news_section(title, news_list, emoji="📌"):
    if not news_list:
        return f"### {emoji} {title}\n接口获取失败\n"
    lines = [f"### {emoji} {title}"]
    for idx, item in enumerate(news_list, 1):
        item = item[:120] + "..." if len(item) > 120 else item
        lines.append(f"{idx}. {item}")
    return "\n".join(lines) + "\n"

# ================== 钉钉推送 ==================
def send_to_dingtalk(content_markdown):
    if not DINGTALK_WEBHOOK:
        print("❌ DINGTALK_WEBHOOK 未设置")
        return False

    webhook_url = DINGTALK_WEBHOOK
    if DINGTALK_SECRET:
        timestamp = str(round(time.time() * 1000))
        secret_enc = DINGTALK_SECRET.encode("utf-8")
        string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}".encode("utf-8")
        sign = urllib.parse.quote_plus(
            base64.b64encode(hmac.new(secret_enc, string_to_sign, hashlib.sha256).digest())
        )
        webhook_url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"

    payload = {"msgtype": "markdown", "markdown": {"title": "国内热点新闻", "text": content_markdown}}
    try:
        resp = requests.post(webhook_url, headers={"Content-Type":"application/json"}, data=json.dumps(payload), timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print("✅ 钉钉推送成功")
            return True
        else:
            print(f"❌ 推送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 推送异常: {e}")
        return False

# ================== 去重缓存 ==================
def load_sent_titles():
    try:
        if not os.path.exists(CACHE_FILE):
            return set()
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    except:
        return set()

def save_sent_titles(titles):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for t in titles:
                f.write(t + "\n")
    except:
        pass

# ================== 主程序 ==================
def main():
    print(f"⏰ 开始抓取国内热点 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sent_titles = load_sent_titles()
    md_content = f"# 🔥 国内热点新闻\n> 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    new_titles = set()
    for source in NEWS_SOURCES:
        news = source["api_func"]()
        news_to_send = [n for n in news if n not in sent_titles]
        new_titles.update(news_to_send)
        md_content += format_news_section(source["name"], news_to_send) + "\n---\n"

    # 钉钉长度限制
    if len(md_content) > 1900:
        md_content = md_content[:1900] + "\n\n...(内容过长已截断)"

    success = send_to_dingtalk(md_content)
    if success:
        save_sent_titles(sent_titles.union(new_titles))

if __name__ == "__main__":
    main()
