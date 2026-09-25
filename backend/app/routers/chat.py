"""问答接口"""
from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.rag.chain import ask

router = APIRouter(prefix="/chat", tags=["chat"])   # 给个合适的 prefix 和 tags

@router.post("", response_model=ChatResponse)   # POST，返回类型用模型声明
def chat(req: ChatRequest):
    answer = ask(req.question)        # 唯一的"业务动作"就这一行
    return ChatResponse(answer=answer)
