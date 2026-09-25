# Day 4：高级 RAG②——HyDE 假设文档检索（2.9~2.11 完成）

## 用时

- 2026-09-09：完成 HyDE 三步——写假设文档生成器（2.9）→ 接入检索器替代原始问题（2.10）→ 对比 HyDE 和基础检索（2.11）。收尾附真实语料实验（临时加 `#深浅拷贝` 主题）。

## 本日做了什么

在基础 RAG 链路上、**检索之前**加了一层"翻译"：用户问题措辞常和文档写法差很远（大白话 vs 术语），直接拿问题去比向量容易失准。HyDE 的思路是**先让 LLM 根据问题虚构一段"假设文档"，再用这段替代原始问题去 FAISS 检索**——LLM 当翻译，把"问题语"翻成"文档语"，让词面重合、提高召回。

新建 `hyde.py`（`generate_hypothesis(question) -> str`），`retriever.py` 加 `use_hypothesis` 开关接入（和 `use_reranker` 同套路）。注意它是检索器**内部**的一步：`similarity_search()` 的 query 从 `question` 换成假设文档，机制没变，只是换了搜索词。

**最终结论（再次反直觉但重要）**：和 rerank 那天一模一样的坎——玩具语料太干净测不出收益。在 6 主题语料上 HyDE 只把正确块从第 2 位提到第 1 位，没有"兜住基础检索漏掉的块"；临时加"问题措辞与文档用词刻意错开"的 `#深浅拷贝` 主题复测，基础检索照样命中（embedding 是语义检索不是关键词检索，语义等价也能匹配）。HyDE 的真正价值（把基础检索漏掉的正确块捞回来）要等大而杂、正确块埋在 top-5 之外的真实语料才显现。

## 目录结构（rag 模块变化）

```
backend/app/rag/
├── hyde.py        # ✅ 新增：generate_hypothesis()——LLM 写假设文档（2.9）
├── prompts.py     # ✅ 改：加 HYDE_PROMPT（system 规定"文档腔"，user 放问题）（2.9）
├── retriever.py   # ✅ 改：retrieve() 加 use_hypothesis 开关（2.10）
└── ...其余模块不变
data/samples/
└── python-basics.txt  # ✅ 改：追加第 7 主题 #深浅拷贝（2.11 真实语料实验）
```

## 执行的关键代码/命令

| 代码/命令 | 解释 |
|-----------|------|
| `PYTHONIOENCODING=utf-8 python -m app.rag.hyde` | 单测假设文档生成（要加编码前缀，否则 Windows 控制台中文乱码） |
| `python -m app.rag.store` | 追加语料后重建向量库（save_local 覆盖同名文件） |
| `python -m app.rag.retriever` | 2.11 A/B：同一错位问题，`use_hypothesis=False/True` 两组对比命中 |

## 核心代码段

### 1. 假设文档提示词（`app/rag/prompts.py`）✅ 2.9

```python
HYDE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """你是一个检索辅助器。用户会给你一个问题，你不需要回答这个问题本身，
        而是虚构一段"可能存在于某份技术文档/教程中的正文段落"，这段话写出来是为了
        帮向量检索找到相关资料。

        要求：
        1. 写成书面、陈述句的教程正文，不要对话腔，不要"我来解释""你可以这样做"这类口吻；
        2. 段落里包含和该主题强相关的关键词；
        3. 只输出正文本身，不要任何开场白、解释或结尾。""",
    ),
    ("user", "问题：{question}\n\n请写出对应的假设文档段落："),
])
```

设计要点：**目的不是回答用户，是写"看起来像文档的一段话"**。三条要求分别管——①文档腔（否则退化成"答案腔"，词面照样离文档远）、②关键词（让假设文档和库文档用词重合，这是命中的根本）、③只输出正文（任何多余的字都会污染这次要拿去比向量的文本）。最容易写错的点：prompt 一旦诱导模型"回答这个问题"，HyDE 就失去意义。

### 2. 假设文档生成器（`app/rag/hyde.py`）✅ 2.9

```python
"""假设文档检索器(HyDE)：
   问题 → LLM 写一段"像文档的段落" → 这段代替原始问题去检索。
   为什么能更准：用户问话和文档写法是两种"语言"，LLM 当翻译。"""
from app.utils.llm import call_llm
from app.rag.prompts import HYDE_PROMPT

def generate_hypothesis(question: str) -> str:
    # ① 填模板：format_messages 返回消息对象列表（system + user 两条）
    msg_objs = HYDE_PROMPT.format_messages(question=question)
    # ② 转 dict（human→user，和 chain.py 同一个坑）再调 call_llm
    messages = [
        {"role": "user" if m.type == "human" else m.type, "content": m.content}
        for m in msg_objs
    ]
    # ③ 去掉首尾空白返回
    return call_llm(messages).strip()
```

结构上和 reranker.py 最大的区别：**hyde.py 不需要自己发 HTTP 请求**。rerank 是硅基流动的独立 API 所以要自己写 `requests.post`；而 HyDE 用的是同一个 Chat API，直接复用已封装好的 `call_llm()` 即可。

### 3. 接入检索器（`app/rag/retriever.py`）✅ 2.10

```python
def retrieve(question: str, k: int = RETRIEVER_TOP_K, use_reranker: bool = False,
             use_hypothesis: bool = False) -> list[str]:
    if not store_exists():
        raise ValueError("向量库不存在，请在 backend 目录先运行：python -m app.rag.store")
    vectorstore = load_store()
    # HyDE：开开关就用假设文档替代原问题去比向量
    if use_hypothesis:
        query = generate_hypothesis(question)   # 注意：这里的 query 是"翻译过的文档语"
    else:
        query = question
    docs = vectorstore.similarity_search(query, k=k)
    texts = [doc.page_content for doc in docs]
    if use_reranker:
        ranked = get_reranker().rerank(question, texts)   # ← rerank 的 query 仍是原问题！
        texts = [texts[i] for i, _ in ranked[:RERANK_TOP_K]]
    return texts
```

**最容易踩的坑（要点①）**：HyDE 只管 `similarity_search` 的 query；底下 rerank 的 query **必须继续用原始 `question`**。为什么？假设文档是"凭空编的话"，生成它只为骗过 embedding 的距离计算；而 rerank 是拿 query 和库里真实块逐字判读相关性，拿编的话判不如拿用户真问题判准。所以两处 query 不同源——embedding 用"翻译版"，rerank 用"原版"。

## 犯的错 & 解决方法

| 错误信息 | 原因 | 解决方式 |
|---------|------|---------|
| `AttributeError: 'tuple' object has no attribute 'format_messages'` | 定义 HYDE_PROMPT 时**结尾多写了一个逗号**：`HYDE_PROMPT = ChatPromptTemplate.from_messages([...]),`——尾随逗号让 Python 把右边整体包成单元素元组 | 删掉行尾逗号；对比 `type()` 确认是 `ChatPromptTemplate` 而非 `tuple` |
| 参数名 `use_hythesis` 拼错（漏了 p） | 手误；函数能跑是因为 __main__ 里调用处拼了同一个错名，"错得一致" | 改成 `use_hypothesis`，三处（签名/判断/调用）同步改；错名极难读，且和 `hyde.py` 的规范命名对不上 |

## 本日知识点归纳

- **HyDE 治的是"召回端"，rerank 治的是"排序端"**：rerank 把粗筛捞回来的候选排干净（正确块在 3~8 位时有效）；HyDE 让该被捞的块别漏在粗筛外（原问句根本搜不到时有效）。两者流水线前后站，不冲突
- **HyDE 机制上没有新东西**：只是把 `similarity_search()` 的 query 从原问题换成 LLM 生成的假设文档——它没引入新检索机制，"翻译"才是全部价值
- **问题语 ≠ 文档语是检索失准的根源**：用户问"程序崩了想让它继续跑"，库里写"try/except 捕获异常"。词面零交集 → 向量距离远 → 漏
- **embedding 是语义检索不是关键词检索**：所以"改了备份原数据也变"这种语义等价，即便不含"拷贝/copy"也能命中——这让"构造基础检索必漏的问题"在干净语料上很难
- **假设文档是"脏文本"来源之一**：LLM 偶尔溢出与指令不符的句子（实测本次输出干净，但 prompt 约束不是 100% 可靠，工程上要容忍/清洗）
- **真实语料实验**：问题词≠文档词还不够，语料必须"大而杂"（几十上百段、主题相近、正确块埋在 top-5 外）才有 HyDE 的用武之地——和 rerank 的结论同源：**玩具语料测技术点收益是规模问题**
- **尾随逗号陷阱**：`x = 表达式,` 会把右边包成元组，定义多行模板/调用时行尾多一个逗号就是 bug

## 面试常见问题

Q: 什么是 HyDE？它解决什么问题？（2.11）
A: HyDE（假设文档检索）是"先让 LLM 根据问题虚构一段假设文档，再用它替代原始问题去向量检索"。解决"问题措辞和库文档写法差别大导致向量检索失准"——LLM 当翻译，把用户大白话翻成文档语，让词面重合、提升召回。

Q: HyDE 和 Rerank 都提升准确率，本质区别？
A: 治的环节不同。Rerank 是排序端，对粗筛结果二次精排，解决"捞回来的不对"；HyDE 是召回端，让正确块别在粗筛阶段就被漏掉，解决"该捞的没捞到"。先 HyDE 保证别漏，再 Rerank 保证进 LLM 的都是真的。

Q: 为什么 HyDE 里 embedding 检索用假设文档，而 rerank 的 query 还用原始问题？
A: 两者用途不同。假设文档是"凭空编的"，只为让 embedding 的距离计算命中——它是给向量库看的搜索词；rerank 是拿 query 和真实块逐字判读，用原始问题（用户的真实意图）判更准。所以假设文档只替换 embedding 那一段的 query。

Q: 用了 HyDE，向量库的文档需要额外处理吗？
A: 不需要。HyDE 只在检索侧加了一步"生成假设文档"，文档侧照常加载、切分、建库。这也是它工程上便宜的原因——改 query，不动库。

## 练习题

1. 把 `#深浅拷贝` 那段从语料里临时去掉、重建库，再用"我做了个备份，改备份时原数据也变了"这个问题测 `use_hypothesis=False/True`——对比这次和保留该主题时，基础检索有没有从"命中"变"漏掉"
2. 思考：为什么 rerank 的 query 必须用原始问题而不是假设文档？如果两处都用假设文档，可能出现什么坏结果？
3. 用 `HYDE_PROMPT.format_messages(...)` 打印一下生成的 system 和 user 两条消息原文，观察 user 消息是怎么把问题嵌进模板的
4. （选做）把 `use_hypothesis=True, use_reranker=True` 一起打开跑 `python -m app.rag.chain`，确认两步串起来链路不报错
5. 复习：`x = 表达式,` 和 `x = (表达式,)` 以及 `x = 表达式` 三者的类型分别是什么？用 `type()` 验证

## 下一步做什么

HyDE 完成（实现 + 接入 + 玩具语料局限结论已记录），至此**高级 RAG 的检索增强两个技术点（HyDE + Rerank）都已落地**。剩下计划内：PDF 加载器、三种切分方式对比（仍暂缓）；接着是 **RAGAS 评估（2.15~2.17）**——量化 RAG 好坏，Faithfulness 等指标 ≥ 阈值，正好能回答"怎么证明 HyDE/Rerank 有效"这个一直绕不开的问题（评估需要更大更真实的评估集，会是后续真正的语料升级点）。或按原计划先切 **Step 3：Vue3 前端（聊天界面 + 文件上传 + 部署）**。
