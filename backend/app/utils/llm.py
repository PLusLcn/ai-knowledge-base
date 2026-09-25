"""
LLM API 调用封装（原生 requests 版）
为什么要先用 requests 而不是 LangChain？
- 看清 API 调用的本质：就是发一个 HTTP POST 请求
- 知道 LangChain 在底层帮你做了什么
"""

import requests
import json
from typing import Optional

from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, LLM_MODEL


def call_llm(
    messages: list[dict],
    system_prompt: Optional[str] = None,
    model: str = LLM_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    
) -> str:
    """
    调用硅基流动的 LLM API
    
    参数：
        messages: 消息列表，格式 [{"role": "user", "content": "你好"}]
        model: 模型名
        temperature: 温度（越高越随机）
        max_tokens: 最大输出长度
    返回：
        LLM 返回的文本内容
    """
    url = f"{SILICONFLOW_BASE_URL}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()  # 非 200 状态码直接抛异常
    
    result = response.json()
    return result["choices"][0]["message"]["content"]

def call_llm_stream(
        messages: list[dict],
        system_prompt: Optional[str] = None,
        model: str = LLM_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2048,        
    ):
    """
    流式调用LLM，逐字yield返回内容
    """
    url = f"{SILICONFLOW_BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    response = requests.post(url, headers=headers, json=payload, stream=True)
    response.raise_for_status()  # 非 200 状态码直接抛异常
    
    for line in response.iter_lines():
        if not line:
            continue
        line_text = line.decode("utf-8").strip()
        if not line_text.startswith("data: "):
            continue
        if line_text == "data: [DONE]":
            break
        try:
            chunk = json.loads(line_text[6:])
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content
        except json.JSONDecodeError:
            continue  # 跳过无法解析的行

    

# ---------- 测试 ----------
# if __name__ == "__main__":
#     reply = call_llm(
#         messages=[{"role": "user", "content": "Python 和 Java 哪个好学？"}],
#         system_prompt="你是一个耐心教导初学者的编程老师，用简单的话解释"
#     )

#     print("LLM 回复：", reply)
if __name__ == "__main__":
    print("LLM 回复：", end="", flush=True)
    for chunk in call_llm_stream(
        messages=[{"role": "user", "content": "Python 和 Java 哪个好学？二十字以内"}],
        system_prompt="你是一个耐心教导初学者的编程老师，用简单的话解释"
    ):
        print(chunk, end="", flush=True)
    print()
