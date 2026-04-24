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

# ================== 🔐 配置区域 ==================
# 从环境变量读取钉钉机器人信息 (在 GitHub Secrets 中配置)
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}
# ===============================================


def fetch_multi_source_hot(limit=12):
    """
    从多个热搜源依次获取数据，优先返回第一个成功获取的源，并进行标题去重
    数据源：微博、知乎、头条、B站、抖音、百度
    """
    hot_apis = [
        {"name": "微博热搜", "url": "https://60s.viki.moe/v2/hot/weibo"},
        {"name": "知乎热榜", "url": "https://60s.viki.moe/v2/hot/zhihu"},
        {"name": "头条热搜", "url": "https://60s.viki.moe/v2/hot/toutiao"},
        {"name": "B站热搜", "url": "https://60s.viki.moe/v2/hot/bilibili"},
        {"name": "抖音热搜", "url": "https://60s.viki.moe/v2/hot/douyin"},
        {"name": "百度热搜", "url": "https://60s.viki.moe/v2/hot/baidu"},
    ]

    for source in hot_apis:
        try:
            resp = requests.get(source["url"], headers=HEADERS, timeout=10)
            data = resp.json()
            items = data.get("data", [])
            if not items:
                print(f"⚠️ {source['name']} 返回数据为空，尝试下一个源...")
                continue

            # 去重并保留顺序
            seen = set()
            hot_list = []
            for item in items:
                title = item.get("title", "")
                if title and title not in seen:
                    seen.add(title)
                    hot_list.append(title)
                if len(hot_list) >= limit:
                    break

            if hot_list:
                print(f"✅ 成功从 {source['name']} 获取到 {len(hot_list)} 条热点")
                return hot_list
            else:
                print(f"⚠️ {source['name']} 没有有效标题，尝试下一个源...")
        except Exception as e:
            print(f"❌ {source['name']} 连接失败: {str(e)}，尝试下一个源...")

    # 所有源都失败
    return ["❌ 所有热搜源均无法获取数据，请检查网络或稍后重试"]


def format_news_section(title, news_list, emoji="🔥"):
    """格式化新闻列表为 Markdown 区块"""
    if not news_list:
        return f"### {emoji} {title}\n暂无数据\n"

    lines = [f"### {emoji} {title}"]
    for idx, item in enumerate(news_list, 1):
        # 限制长度
        item = item[:120] + "..." if len(item) > 120 else item
        lines.append(f"{idx}. {item}")
    return "\n".join(lines) + "\n"


def send_to_dingtalk(content_markdown):
    """通过钉钉机器人发送 Markdown 消息（支持加签）"""
    if not DINGTALK_WEBHOOK or not DINGTALK_SECRET:
        print("❌ 错误：未设置钉钉 Webhook 或 Secret")
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
            "title": "全网热点热搜",
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
    print(f"⏰ 开始抓取全网热点 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    hot_news = fetch_multi_source_hot(limit=12)

    # 构造 Markdown 消息
    md_content = f"# 🔥 全网热点热搜\n> 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += format_news_section("综合热搜榜", hot_news, "📊")
    md_content += "\n---\n> 🤖 数据来源: 微博/知乎/头条/B站/抖音/百度 · 推送由 GitHub Actions 自动完成"

    # 钉钉消息长度限制约 2000 字符
    if len(md_content) > 1900:
        md_content = md_content[:1900] + "\n\n...(内容过长已截断)"

    send_to_dingtalk(md_content)


if __name__ == "__main__":
    main()
