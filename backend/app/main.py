from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, document
from app.config import API_V1_PREFIX

app = FastAPI(title="AI知识库问答系统", version="0.1.0")

# 跨域设置（允许前端开发时访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix=API_V1_PREFIX)
app.include_router(document.router, prefix=API_V1_PREFIX)


@app.get(f"{API_V1_PREFIX}/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "message": "服务运行正常"}




