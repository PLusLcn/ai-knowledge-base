# Day 1：Step 1 理解 RAG + 调通 LLM API（1.1~1.8）

## 用时

实际：多次会话累计完成（待补） / 预估：3-4 天

## 本日做了什么

从零到一跑通 RAG 最小闭环：调通 LLM API → 封装 → Prompt 模板 → 嵌入 → FAISS 检索 → 完整问答链。

## 执行的关键代码/命令

| 代码/命令 | 解释 |
|-----------|------|
| `cd backend && source venv/Scripts/activate` | 进入后端目录 + 激活虚拟环境 |
| `python test_llm.py` | requests 直调 DeepSeek-V3，验证 API 连通 |
| `python test_langchain_llm.py` | LangChain `ChatOpenAI` 调通硅基流动 |
| `python app/rag/prompts.py` | 验证 `ChatPromptTemplate` 填充 |
| `python test_embedding_custom.py` | 自定义嵌入类，验证嵌入 API |
| `python test_faiss.py` | FAISS 建库 + 相似度检索 |
| `python test_rag.py` | 完整 RAG 链问答 |

## 核心代码段

### 1. LLM API 封装（`app/utils/llm.py`）

```python
def call_llm(messages, system_prompt=None, model=LLM_MODEL,
             temperature=0.7, max_tokens=2048) -> str:
    url = f"{SILICONFLOW_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}",
               "Content-Type": "application/json"}
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

### 2. Prompt 模板（`app/rag/prompts.py`）

```python
RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个知识库问答助手。\n请严格基于下面的参考资料回答问题，"
               "如果资料里没有答案，就明确说不知道。\n\n参考资料：\n{context}"),
    ("user", "{question}"),
])
```

### 3. 自定义嵌入类（`test_embedding_custom.py` 起，后续进 `app/rag/embedder.py`）

```python
class SiliconFlowEmbeddings(Embeddings):
    def embed_documents(self, texts):
        resp = requests.post(f"{self.base_url}/embeddings",
                             headers={...}, json={"model": self.model, "input": texts})
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    def embed_query(self, text):
        return self.embed_documents([text])[0]
```

### 4. 完整 RAG 链（`test_rag.py`）

```python
def ask(question: str) -> str:
    results = vectorstore.similarity_search(question, k=2)
    context = "\n\n".join([doc.page_content for doc in results])
    msg_objs = RAG_PROMPT.format_messages(context=context, question=question)
    messages = [{"role": "user" if m.type == "human" else m.type,
                 "content": m.content} for m in msg_objs]
    return call_llm(messages)
```

## 犯的错 & 解决方法

| 错误信息 | 原因 | 解决方式 |
|---------|------|---------|
| `OpenAIEmbeddings` 400 `code 20015` | langchain-openai 用 tiktoken 把文本编码成 token 数字数组作为 `input` 发送，硅基流动不支持 | 写自定义 `SiliconFlowEmbeddings`（requests 直调，发文本字符串） |
| `call_llm` 400（LLM 端点） | LangChain 消息 `role` 是 `human`，API 只认 `system/user/assistant` | 转换时把 `human` 映射成 `user` |

完整细节见 [error-log.md](error-log.md)。

## 本日知识点归纳

- **RAG 5 环节**：加载文档 → 切分 → 向量化 → 检索 → 生成（本日完成向量化/检索/生成）
- **LLM 调用本质**：一次 HTTP POST，LangChain 只是封装
- **嵌入 Embedding**：文字 → 1024 维数字列表，`bge-large-zh-v1.5`
- **FAISS**：`from_documents(docs, embeddings)` 一步完成向量化 + 建索引
- **相似度检索**：`similarity_search(query, k)` 问题转向量后取最近 k 段
- **ChatPromptTemplate**：system 段放指令/资料，user 段放问题
- **Document**：`page_content` + `metadata`
- **`if __name__ == "__main__"`**：直接运行才执行测试代码，被 import 时不执行

## 面试常见问题

Q: 什么是 RAG？为什么需要它？
A: 检索增强生成。先检索相关资料，再让 LLM 基于资料回答，减少"编造"（幻觉），比直接问 LLM 更准确。

Q: 嵌入和生成有什么区别？
A: 嵌入把文字转成数字向量用于检索（判断语义相似）；生成是让 LLM 产生新文字用于回答。

Q: FAISS 是怎么找到相似内容的？
A: 把问题和所有文档都转成向量，算向量距离，返回距离最近的 k 段。

Q: 为什么先学 requests 再学 LangChain？
A: 看清本质。LangChain 只是把"构造请求 → 发 HTTP → 解析响应"封装起来了，底层还是 requests 做的事。

Q: 检索结果不相关怎么办？
A: 可以加大 k、优化文档切分，或引入重排序（Rerank）、假设文档检索（HyDE）——Step 2 会做。

## 练习题（之后完成）

1. 给 `ask()` 加一个可选参数 `system_prompt`，调用时能覆盖默认指令
2. 把 `k` 改成 3 再跑一次，观察回答差异
3. 给示例文档加 `metadata={"来源": "xxx"}`，检索时打印 `doc.metadata`
4. 用 `call_llm_stream` 改造 `ask()`，实现逐字输出
5. 在 `docs/error-log.md` 补一条新报错记录（格式照抄已有条目）

## 下一步做什么

Step 2：加载真实文档（PDF/TXT + 文本分割）→ 封装 FastAPI 问答接口 → 高级检索（HyDE/Rerank）。
