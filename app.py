import os
import threading
import time
import webbrowser

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PROVIDER_CONFIG = {
    "openrouter": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "models_url": "https://openrouter.ai/api/v1/models",
        "requires_auth": True,
    },
    "deepseek": {
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "models_url": None,
        "requires_auth": True,
    },
}

PREDEFINED_MODELS = {
    "deepseek": ["deepseek-chat", "deepseek-coder"],
}

valid_models_cache = {}


def get_valid_models(provider, api_key):
    if provider in valid_models_cache:
        return valid_models_cache[provider]

    if provider in PREDEFINED_MODELS:
        valid_models_cache[provider] = PREDEFINED_MODELS[provider]
        return PREDEFINED_MODELS[provider]

    config = PROVIDER_CONFIG.get(provider)
    if not config or not config.get("models_url"):
        return []

    try:
        headers = {}
        if config.get("requires_auth") and api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(config["models_url"], headers=headers)
        response.raise_for_status()
        data = response.json()

        if provider == "openrouter":
            valid_models = {model["id"] for model in data.get("data", [])}
            valid_models_cache[provider] = list(valid_models)
            return list(valid_models)
        else:
            valid_models = [model["id"] for model in data.get("data", [])]
            valid_models_cache[provider] = valid_models
            return valid_models
    except Exception as e:
        print(f"获取{provider}模型列表失败: {str(e)}")
        return []


def validate_model(model_id, provider, api_key):
    valid_models = get_valid_models(provider, api_key)
    if not valid_models:
        return True
    return model_id in valid_models


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/models", methods=["GET"])
def models():
    try:
        provider = request.headers.get("X-Provider", "openrouter")
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "")

        valid_models = get_valid_models(provider, api_key)
        return jsonify({"models": sorted(valid_models)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    model = data.get("model", "openai/gpt-3.5-turbo")
    provider = request.headers.get("X-Provider", "openrouter")

    auth_header = request.headers.get("Authorization", "")
    api_key = auth_header.replace("Bearer ", "")

    print(f"收到请求 - 提供方: {provider} - 模型: {model}")
    print(f"消息数量: {len(messages)}")
    print(f"对话历史:")
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        name = msg.get("name", "")
        content = msg.get("content", "")[:100]
        print(f"  [{i}] {role} ({name}): {content}...")
    print(f"API Key: {api_key[:20]}..." if api_key else "API Key: 未设置")

    config = PROVIDER_CONFIG.get(provider)
    if not config:
        error_msg = f"不支持的提供方: {provider}"
        print(f"错误: {error_msg}")
        return jsonify({"error": error_msg}), 400

    if config.get("requires_auth") and not api_key:
        error_msg = f"{provider}需要API Key，请在页面中设置"
        print(f"错误: {error_msg}")
        return jsonify({"error": error_msg}), 400

    if not validate_model(model, provider, api_key):
        error_msg = f"无效的模型ID: {model}"
        print(f"错误: {error_msg}")
        return jsonify({"error": error_msg}), 400

    headers = {
        "Content-Type": "application/json",
    }

    if config.get("requires_auth") and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    api_url = config["api_url"]
    payload = {"model": model, "messages": messages}

    try:
        print(f"正在向 {provider} 发送请求...")
        print(f"API URL: {api_url}")
        response = requests.post(api_url, headers=headers, json=payload)
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
