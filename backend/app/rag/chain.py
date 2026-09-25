"""RAG 问答链：检索 → 拼上下文 → 填模板 → 调 LLM，一次 ask 完成问答"""
from typing import Optional
from app.config import RETRIEVER_TOP_K
from app.rag.retriever import retrieve
from app.rag.prompts import RAG_PROMPT
from app.utils.llm import call_llm

def ask(question: str, k: int = RETRIEVER_TOP_K, system_prompt: Optional[str] = None) -> str:
    # ① 检索：retrieve() 返回相关块的 list[str]
    chunks = retrieve(question, k=k)

    # ② 拼 context：多块用 "\n\n" 拼成一个字符串（test_rag 里抄）
    context = "\n\n".join(chunks)

    if system_prompt is None:
            # ③ 填模板：RAG_PROMPT.format_messages(context=..., question=...)           
            msg_objs = RAG_PROMPT.format_messages(context=context, question=question)
        
            # ④ 转 dict（human→user，Step1 踩过的坑）+ call_llm
            messages = [{"role": "user" if m.type == "human" else m.type, "content": m.content} for m in msg_objs]
            return call_llm(messages)
    else:
        # 覆盖人设：不用模板，直接用传入的 system + 不带资料（闲聊场景不需要硬塞 context）
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        return call_llm(messages)

if __name__ == "__main__":
    # print(ask("什么是闭包？"))            # 库里没专门讲闭包
    # print("-" * 40)
    # print(ask("Python 的 GIL 是什么？"))  # 库里没有
    # 闲聊场景：覆盖人设，不带资料
    # , system_prompt="你是一个热情的闲聊助手，简单打招呼，二十字以内")
     print(ask("今晚吃什么"))
