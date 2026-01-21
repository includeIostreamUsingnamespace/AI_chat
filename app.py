import os
import threading
import time
import webbrowser

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

valid_models_cache = None


def get_valid_models(api_key):
    global valid_models_cache
    if valid_models_cache is not None:
        return valid_models_cache

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.get(OPENROUTER_MODELS_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        valid_models_cache = {model["id"] for model in data.get("data", [])}
        return valid_models_cache
    except Exception as e:
        print(f"获取模型列表失败: {str(e)}")
        return set()


def validate_model(model_id, api_key):
    valid_models = get_valid_models(api_key)
    if not valid_models:
        return True
    return model_id in valid_models


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/models", methods=["GET"])
def models():
    try:
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
        valid_models = get_valid_models(api_key)
        return jsonify({"models": sorted(valid_models)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    model = data.get("model", "openai/gpt-3.5-turbo")

    auth_header = request.headers.get("Authorization", "")
    api_key = auth_header.replace("Bearer ", "")

    print(f"收到请求 - 模型: {model}")
    print(f"消息数量: {len(messages)}")
    print(f"对话历史:")
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        name = msg.get("name", "")
        content = msg.get("content", "")[:100]
        print(f"  [{i}] {role} ({name}): {content}...")
    print(f"API Key: {api_key[:20]}..." if api_key else "API Key: 未设置")

    if not api_key:
        error_msg = "未提供API Key，请在页面中设置"
        print(f"错误: {error_msg}")
        return jsonify({"error": error_msg}), 400

    if not validate_model(model, api_key):
        error_msg = f"无效的模型ID: {model}"
        print(f"错误: {error_msg}")
        return jsonify({"error": error_msg}), 400

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "AI Chat",
    }

    payload = {"model": model, "messages": messages}

    try:
        print(f"正在向 OpenRouter 发送请求...")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        print(f"响应状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"错误响应: {response.text}")

        response.raise_for_status()
        result = response.json()
        print(f"请求成功")
        return jsonify(result)
    except Exception as e:
        print(f"错误详情: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/user-message", methods=["POST"])
def user_message():
    data = request.json
    messages = data.get("messages", [])

    print(f"收到用户消息")
    print(f"消息内容: {messages[-1].get('content', '')}")

    return jsonify({"success": True})


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)
