"""问答接口的请求/响应模型"""
from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str    # 用户的问题

class ChatResponse(BaseModel):
    answer: str      # 模型回答
