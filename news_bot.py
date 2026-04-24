#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import hmac
import json
import hashlib
import base64
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ================== 配置 ==================
# 从环境变量读取钉钉机器人信息（GitHub Actions Secrets 中配置）
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")

# 请求头，模拟浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}
# =========================================


def fetch_zhihu_hot(limit=10):
    """通过每日热榜API获取知乎热榜"""
    # 使用公益的 DailyHot API 服务，无需鉴权
    api_url = "https://api.vvhan.com/api/hotlist/zhihu"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        data = resp.json()
        
        if data.get("success"):
            news_list = []
            for item in data.get("data", [])[:limit]:
                title = item.get("title", "")
                # 你可以在这里自由添加其他字段，如热度值等
                # hot_score = item.get("hot", "")
                if title:
                    news_list.append(f"{title}")
            if not news_list:
                return ["⚠️ 知乎热榜暂无数据，请稍后重试"]
            return news_list
        else:
            return [f"❌ 知乎热榜API异常: {data.get('message', '未知错误')}"]
    except Exception as e:
        return [f"❌ 知乎热榜API连接异常: {str(e)}"]


def fetch_reddit_hot(limit=10):
    """抓取 Reddit 热门帖子（国际热点）"""
    url = "https://www.reddit.com/r/all/top.json?limit={limit}&t=day" + str(limit)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        hot_list = []
        for post in posts:
            title = post.get("data", {}).get("title", "")
            # 简单过滤掉广告或过短的标题
            if title and len(title) > 5:
                hot_list.append(title)
        if not hot_list:
            return ["⚠️ Reddit 热门抓取失败（可能API变动）"]
        return hot_list
    except Exception as e:
        return [f"❌ Reddit 异常: {str(e)}"]


def format_news_section(title, news_list, emoji="📌"):
    """将新闻列表格式化为 Markdown 区块"""
    if not news_list:
        return f"### {emoji} {title}\n暂无数据\n"
    lines = [f"### {emoji} {title}"]
    for idx, item in enumerate(news_list, 1):
        # 防止标题过长影响阅读
        item = item[:120] + "..." if len(item) > 120 else item
        lines.append(f"{idx}. {item}")
    return "\n".join(lines) + "\n"


def send_to_dingtalk(content_markdown):
    """通过钉钉机器人发送 Markdown 消息（支持加签安全设置）"""
    if not DINGTALK_WEBHOOK or not DINGTALK_SECRET:
        print("❌ 错误：未设置 DINGTALK_WEBHOOK 或 DINGTALK_SECRET 环境变量")
        return False

    timestamp = str(round(time.time() * 1000))
    secret_enc = DINGTALK_SECRET.encode("utf-8")
    string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

    webhook_url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "实时热点新闻",
            "text": content_markdown
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
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


def main():
    print(f"⏰ 开始抓取新闻 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 抓取国内热点（知乎）
    domestic = fetch_zhihu_hot(limit=8)
    # 抓取国际热点（Reddit）
    international = fetch_reddit_hot(limit=8)

    # 构造 Markdown 消息
    md_content = f"# 🔥 每日热点新闻\n> 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += format_news_section("🇨🇳 国内·知乎热榜", domestic, "📰")
    md_content += "\n---\n\n"
    md_content += format_news_section("🌍 国际·Reddit 热门", international, "🌐")
    md_content += "\n---\n> 🤖 推送由 GitHub Actions 自动完成"

    # 限制总长度 (钉钉 Markdown 限制为 2000 字符以内，稍作截断)
    if len(md_content) > 1900:
        md_content = md_content[:1900] + "\n\n...(内容过长已截断)"

    # 发送到钉钉
    success = send_to_dingtalk(md_content)
    if success:
        print("🎉 任务执行完毕")
    else:
        print("⚠️ 任务执行完成，但推送未成功")


if __name__ == "__main__":
    main()
