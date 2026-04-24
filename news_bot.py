import os
import requests
import json
from datetime import datetime

# ------------------------------
# 配置部分
# ------------------------------
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")  # GitHub Secrets 里配置
NEWS_API_KEY = os.getenv("NEWS_API_KEY")          # 聚合数据 API Key
NEWS_API_URL = "http://v.juhe.cn/toutiao/index"  # 今日头条聚合数据 API 示例

# ------------------------------
# 获取新闻
# ------------------------------
def get_news():
    params = {
        "key": NEWS_API_KEY,
        "type": "top"  # 热点新闻
    }
    try:
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        data = response.json()
        if data['error_code'] != 0:
            return f"获取新闻失败: {data.get('reason', '未知原因')}"
        
        news_items = data['result']['data'][:5]  # 取前5条新闻
        message = f"### 今日新闻热点 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        for item in news_items:
            message += f"- [{item['title']}]({item['url']})\n"
        return message
    except Exception as e:
        return f"获取新闻异常: {e}"

# ------------------------------
# 推送到钉钉
# ------------------------------
def send_to_dingtalk(message):
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "每日新闻热点",
            "text": message
        }
    }
    try:
        r = requests.post(DINGTALK_WEBHOOK, headers=headers, data=json.dumps(payload), timeout=5)
        return r.text
    except Exception as e:
        return f"发送钉钉异常: {e}"

# ------------------------------
# 主程序
# ------------------------------
if __name__ == "__main__":
    news_message = get_news()
    result = send_to_dingtalk(news_message)
    print(result)
