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
# 从环境变量读取敏感信息 (在 GitHub Secrets 中配置)
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")
JUHE_NEWS_API_KEY = os.getenv("JUHE_NEWS_API_KEY")  # 聚合数据 AppKey

# 请求头，模拟浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}
# ===============================================


def fetch_juhe_top_news(limit=10, category="top"):
    """
    从聚合数据 API 获取新闻头条

    :param limit: 获取的新闻条目数量
    :param category: 新闻类别，默认为 'top' (头条)，
                     可选: guonei(国内), guoji(国际), keji(科技), caijing(财经), yule(娱乐), tiyu(体育) 等
    :return: 新闻标题列表
    """
    if not JUHE_NEWS_API_KEY:
        return ["❌ 错误: 未设置聚合数据 APPKey，请在 GitHub Secrets 中配置 JUHE_NEWS_API_KEY"]

    # 聚合数据新闻头条 API 地址及参数
    api_url = "http://v.juhe.cn/toutiao/index"
    params = {
        "key": JUHE_NEWS_API_KEY,
        "type": category,  # 新闻类别，top 为头条推荐
    }

    try:
        resp = requests.get(api_url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()

        # API 返回格式: {"reason": "...", "result": {"stat": "1", "data": [...]}}
        if data.get("error_code") == 0 or data.get("reason") == "成功的返回":
            # 兼容不同返回格式，有的接口用 error_code，有的用 result
            result_data = data.get("result", {})
            news_list_raw = result_data.get("data", [])

            if not news_list_raw:
                return ["⚠️ 聚合数据暂无新闻数据，请稍后重试"]

            hot_list = []
            for item in news_list_raw[:limit]:
                title = item.get("title", "")
                if title:
                    hot_list.append(title)

            if hot_list:
                return hot_list
            else:
                return ["⚠️ 未获取到有效新闻标题"]
        else:
            # 如果请求失败，打印具体原因
            error_msg = data.get("reason", data.get("error_code", "未知错误"))
            return [f"❌ 聚合数据 API 请求失败: {error_msg}"]

    except requests.exceptions.RequestException as e:
        return [f"❌ 网络请求异常: {str(e)}"]
    except json.JSONDecodeError:
        return ["❌ 解析 API 返回数据失败，请检查网络或稍后重试"]


def format_news_section(title, news_list, emoji="📌"):
    """将新闻列表格式化为 Markdown 区块"""
    if not news_list:
        return f"### {emoji} {title}\n暂无数据\n"

    lines = [f"### {emoji} {title}"]
    for idx, item in enumerate(news_list, 1):
        # 限制标题长度，避免过长影响阅读
        item = item[:120] + "..." if len(item) > 120 else item
        lines.append(f"{idx}. {item}")
    return "\n".join(lines) + "\n"


def send_to_dingtalk(content_markdown):
    """通过钉钉机器人发送 Markdown 消息（支持加签安全设置）"""
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
            "title": "国内热点新闻",
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
            print(f"❌ 钉钉推送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 推送异常: {e}")
        return False


def main():
    print(f"⏰ 开始抓取新闻 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取不同类别的新闻，可以根据需要调整
    news_top = fetch_juhe_top_news(limit=10, category="top")   # 头条推荐
    news_domestic = fetch_juhe_top_news(limit=5, category="guonei")  # 国内新闻

    # 构造 Markdown 消息
    md_content = f"# 🔥 每日热点新闻\n> 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += format_news_section("聚合精选 (Top Stories)", news_top, "🔥")
    md_content += "\n---\n\n"
    md_content += format_news_section("国内新闻 (Domestic)", news_domestic, "🇨🇳")
    md_content += "\n---\n> 🤖 数据由 聚合数据 提供 · 推送由 GitHub Actions 自动完成"

    # 钉钉 Markdown 消息长度限制约 2000 字符，做安全截断
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
