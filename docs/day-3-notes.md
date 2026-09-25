# Day 3：高级 RAG①——BGE-Rerank 重排序（2.12~2.14 完成）

## 用时

- 2026-09-07：完成 rerank 三步——调通 rerank API（2.12）→ 接入"检索→重排序"流水线（2.13）→ 对比加/不加 rerank（2.14）

## 本日做了什么

在基础 RAG 链路上加了一层**精排**：向量库先粗筛出 top-5，再用硅基流动的 `BAAI/bge-reranker-v2-m3` 对每块打分，只留分数最高的 3 块（`RERANK_TOP_K`）进 LLM。新建 `reranker.py`（封装 rerank API，仿 embedder 的类 + 工厂写法），`retriever.py` 加 `use_reranker` 开关接入精排。

**最终结论（反直觉但重要）**：在这份 6 主题玩具语料上，rerank 的"重排"看不出收益——因为主题太干净，向量检索第 1 名已经命中正确块。rerank 的真正价值（把埋在粗筛第 3~8 位的正确块提上来）要等大而杂的真实语料才显现。分数本身是新的质检维度，但跨 query 不可比，绝对阈值是坑。

## 目录结构（rag 模块变化）

```
backend/app/rag/
├── reranker.py    # ✅ 新增：SiliconFlowReranker + get_reranker()（2.12）
├── retriever.py   # ✅ 改：retrieve() 加 use_reranker 开关（2.13）
└── ...其余模块不变
```

## 执行的关键代码/命令

| 代码/命令 | 解释 |
|-----------|------|
| `python -m app.rag.reranker` | 单测 rerank：相关块(装饰器)分高、无关块分低，落差明显 |
| `python - <<'PY' ...`（诊断脚本） | 同一问题分别看"向量距离序"和"rerank 分数序"，对比重排效果 |
| `curl`/浏览器 POST /api/v1/chat | 2.14 对比加不加 rerank 的真实回答（玩具语料下基本一致） |

## 核心代码段

### 1. 重排序器（`app/rag/reranker.py`）✅ 2.12

```python
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
        # ① 发请求：POST /rerank，headers 和 embedder 一模一样
        resp = requests.post(
            f"{self.base_url}/rerank",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "query": query, "documents": documents},
        )
        resp.raise_for_status()
        results = resp.json()["results"]   # 已按 relevance_score 降序排好
        # ② results 只带 index 和 score，不含原文；index 指向原始 documents 里的位置
        return [(item["index"], item["relevance_score"]) for item in results]

def get_reranker():
    """工厂：和 get_embedding() 同一套路，屏蔽构造细节"""
    return SiliconFlowReranker(SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, RERANK_MODEL)
```

接口契约：`POST {base}/rerank`，body=`{model, query, documents}`；响应 `results[].{index, relevance_score}` 已降序，`index` 回查原 documents 位置。`relevance_score` 归一化到 0~1（服务端做的），**别当百分比读，当排序依据读**。

### 2. 精排接入检索器（`app/rag/retriever.py`）✅ 2.13

```python
def retrieve(question: str, k: int = RETRIEVER_TOP_K, use_reranker: bool = False) -> list[str]:
    """把用户问题转成检索，返回命中块原文（开 reranker 时：粗筛 k 块 → 精排留 RERANK_TOP_K 块）"""
    if not store_exists():
        raise ValueError("向量库不存在，请在 backend 目录先运行：python -m app.rag.store")
    vectorstore = load_store()
    docs = vectorstore.similarity_search(question, k=k)   # ② 粗筛
    texts = [doc.page_content for doc in docs]            # ③ 抽原文当候选（rerank 只收纯文本）
    if use_reranker:                                      # ④ 精排：rerank 只给 (下标,分数) 排序
        ranked = get_reranker().rerank(question, texts)   #    必须按 index 回查 texts
        texts = [texts[i] for i, _ in ranked[:RERANK_TOP_K]]
    return texts
```

**语义变化**：开了 rerank 后 `k` 是"粗筛捞多少"，返回条数由 `RERANK_TOP_K`（3）决定，不再等于 `k`。默认 `False` 保住旧行为——为了第 2.14 步能开关对比。

## 犯的错 & 解决方法

| 错误信息 | 原因 | 解决方式 |
|---------|------|---------|
| 500 `ValidationError: ChatResponse.answer ... input None` | `ask()` 的 `system_prompt=None` 分支构造完 messages **漏了 `return call_llm()`**，函数隐式返回 None，None 一路穿透到 Pydantic 校验 | `if` 分支补 `return call_llm(messages)`；顺带发现 `__main__` 只测了 else 分支才没暴露 |
| rerank 请求字段不被识别（把 `documents` 抄成 `input`） | 对照 embedder 改请求体时，URL 改了字段名还停在 `/embeddings` 那套 | rerank 的字段是 `model/query/documents`；改端点时字段要一起核对 |
| `doc.page_content` 对元组取属性会炸 / rerank 结果乱了 | 把 `rerank()` 返回的 `(index, score)` 当成重排好的文档继续用 | rerank **只给排序表不给原文**；留着原文 `texts`，用 index 回查 |
| 把 `similarity_search` 的 `Document` 对象直接喂 rerank | rerank API 只认纯文本 `list[str]` | 先 `[d.page_content for d in docs]` 抽成文本再传 |

## 本日知识点归纳

- **bi-encoder vs cross-encoder**：embedding 是"各编各的向量比距离"（快，只给排序）；rerank 是"把 query 和候选拼一对逐字判读"（慢，给 0~1 相关分）
- **RAG 两段式**：向量粗筛"多捞"保召回 → rerank 精排"少留"保精准——为什么不能直接把 k 调小：正确块可能排在粗筛第 2~5 位，粗暴砍 k 会漏掉
- **rerank 只给排序表，不给原文**：返回 `(原下标, 分数)`，映射回原候选要自己用 index 做——和 embedding 检索"直接拿回文档"最不一样的地方
- **分数跨 query 不可比**：`1+1等于几` 的最高分 0.142 高过库内问题"加功能"的噪音——绝对阈值会误杀，同组内看"落差/悬崖"更可靠
- **玩具语料看不到精排收益**：6 主题太干净，向量第 1 名已命中；rerank 用武之地在"正确块被埋在粗筛 3~8 位"的大而杂语料
- **闲聊拦截不在 rerank**：靠 prompt"没资料就说不知道"兜底（实测已工作）；更稳的是检索前的意图判断
- **`use_xxx` 布尔开关参数**：给函数加开关而不是直接改死行为，是为了能 A/B 对比（2.14），也能让旧调用方不受影响

## 面试常见问题

Q: 为什么有了 embedding 检索还要 rerank？（2.14）
A: embedding 只按向量距离给"谁最近"，但最近 ≠ 相关，且它没有"够不够格"的概念。rerank 是 cross-encoder，把 query 和每个候选拼一对逐字判读，输出相关分。粗筛负责别漏，精排负责别脏。

Q: rerank 和 embedding 检索的编码方式有什么本质区别？
A: bi-encoder 把问题和文档**各自**压成向量比距离，编码时互不参照；cross-encoder 把 query+文档**拼成一对**一起编码，能逐字符对齐判断相关性，所以更准但更慢。

Q: 为什么不能把 top-k 直接调小来省掉 rerank？
A: 向量"最近"≠"真相关"，真相关的那块可能排在粗筛第 2~5 位。调小 k 会在粗筛阶段就漏掉它。rerank 的思路是"先多捞（保证不漏），再精排（保证进 LLM 的都是真的）"。

Q: rerank 的 relevance_score 0.8 代表 80% 相关吗？
A: 不是。分数是模型把原始 logit 归一化到 0~1 的结果，服务端处理，跨 query 不可比。0.8 和 0.05 的落差有区分意义，0.8 和 0.83 的差别没有。

## 练习题

1. 把 rerank 结果打印完整（含 `relevance_score`），对一个库内问题、一个闲聊问题各跑一次，对比两组分数的"形态"（陡崖 vs 缓坡）
2. 思考：为什么代码里 rerank 返回 `(index, score)` 而不是直接返回重排好的文本？改成直接返回文本有什么坏处？
3. `retrieve()` 的 `use_reranker` 默认值改成 `True`，跑一遍 `python -m app.rag.chain` 确认链路不报错，再改回 `False`
4. （选做）试一个"文档里讲了、但问题和原文用词差别很大"的问题，看纯向量检索和加 rerank 后 top-3 的差异

## 下一步做什么

rerank 完成（实现 + 接入 + 适用边界结论已记录）。下一步进 **HyDE（假设文档检索，计划 Day 9 / 2.9~2.11）**：问题 → 先让 LLM 写一段"假设答案" → 用假设文档替代原始问题去检索，解决"问题措辞和文档差别大导致向量检索失准"。PDF 加载 / 三种切分对比仍暂缓。