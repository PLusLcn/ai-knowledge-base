"""检索器：给定问题，从已建好的向量库里取回最相关的 k 块文本"""
from app.config import RETRIEVER_TOP_K,RERANK_TOP_K
from app.rag.store import store_exists, load_store
from app.rag.reranker import get_reranker
from app.rag.hyde import generate_hypothesis


def retrieve(question: str, k: int = RETRIEVER_TOP_K,use_reranker: bool = False,use_hypothesis: bool = False) -> list[str]:
    """把用户问题转成检索，返回命中的前 k 块原文。"""

    if not store_exists():
        raise ValueError("向量库不存在，请在 backend 目录先运行：python -m app.rag.store")
    # ① 拿就绪的向量库 —— load_store() 已经封装了"读盘 + 嵌入"
    vectorstore = load_store()
    # ② 相似度检索，取前 k 个
    # HyDE：开开关就先让 LLM 生成假设文档，用它替代原问题去比向量
    if use_hypothesis:
        query = generate_hypothesis(question)
    else:
        query = question
    docs = vectorstore.similarity_search(query, k=k)
    # ③ 抽原文当候选——rerank 的 API 只收纯文本，不收 Document 对象
    texts = [doc.page_content for doc in docs]
    # ④ 用 reranker 重排序
    if use_reranker:
        reranker = get_reranker()
        ranked = reranker.rerank(question, texts)
        texts = [texts[i] for i, _ in ranked[:RERANK_TOP_K]] # 留分数最高的 3 个
    # ③ 只留原文，转成 list[str]
    return texts

    

if __name__ == "__main__":
    q = "我做了个备份,改备份时原数据也被改了,想保存一个真正独立的副本"
    print("【HyDE 生成的假设文档】")
    print(generate_hypothesis(q))
    print("=" * 50)
    print("【基础检索】")
    for r in retrieve(q, use_hypothesis=False):
        print(r); print("=" * 50)
    print("【HyDE 检索】")
    for r in retrieve(q, use_hypothesis=True):
        print(r); print("=" * 50)
    


