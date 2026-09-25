"""重排序器：把"问题 + 候选块"拼一对让 cross-encoder 打分，按相关度精排
   对比 embedder.py：embedding 是各编各的向量比距离；rerank 是一对一判读"""
import requests
from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, RERANK_MODEL

class SiliconFlowReranker:
    # 普通类就行（embedder 要喂给 FAISS 才继承 Embeddings；rerank 是我们自己调，不需要）
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        # ① 发请求：
        resp = requests.post(
            f"{self.base_url}/rerank",     # ← 改动点①：/rerank
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"},
            json={"model": self.model,"query": query, "documents": documents},
        )
        resp.raise_for_status()
        results = resp.json()["results"]   # 已按分数降序
        # ② 抽成 [(index, score), ...]。坑：results 只带 index 和 score，不含原文
        #    index 指向你传入的 documents 里第几个
        return [(item["index"], item["relevance_score"]) for item in results]         # ← 改动点③：解析 + index 映射

def get_reranker():
    # 把类的三个构造参数全部换成从 config 读的常量
    return SiliconFlowReranker(SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, RERANK_MODEL)

if __name__ == "__main__":
    # 验证：拿"怎么给函数加额外功能？"当 query，候选里混入相关(装饰器)和无关(with/异常)块
    # 期望：装饰器相关块分数最高且明显高于无关块——用分数落差感受"score 能当质检"
    reranker = get_reranker()
    query = "怎么给函数加额外功能？"
    docs = [
        "装饰器是一种高阶函数，可以在不改动原函数代码的情况下给函数附加额外功能。",
        "with 语句用于管理资源，保证代码块执行完毕或抛异常后文件会被自动关闭。",
        "生成器用 yield 逐个产出值，适合处理海量数据，因为它不一次性把所有结果放内存。",
    ]
    for idx, score in reranker.rerank(query, docs):
        print(f"score={score:.4f} | 原第{idx+1}块: {docs[idx][:30]}...")
