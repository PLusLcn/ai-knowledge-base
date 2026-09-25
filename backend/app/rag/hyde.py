"""假设文档检索器(HyDE)：
   问题 → LLM 写一段"像文档的段落" → 这段代替原始问题去检索。
   为什么能更准：用户问话和文档写法是两种"语言"，LLM 当翻译。"""
from app.utils.llm import call_llm
from app.rag.prompts import HYDE_PROMPT

def generate_hypothesis(question: str) -> str:
    # ① 填模板：HYDE_PROMPT.format_messages(question=question)，得到一条 user 消息
    msg_objs = HYDE_PROMPT.format_messages(question=question)
    # ② 包成 messages 列表调 call_llm
    messages = [
        {"role": "user" if m.type == "human" else m.type, "content": m.content}
        for m in msg_objs
    ]
    response = call_llm(messages)
    # ③ 去掉首尾空白返回   
    return response.strip()

if __name__ == "__main__":
    hypothesis = generate_hypothesis("什么是装饰器？")
    print(hypothesis)

