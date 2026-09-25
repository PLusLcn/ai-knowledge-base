# Day 2：Step 2 真实文档入库 + 检索 + 问答接口（2.1~2.6 完成）

## 用时

- 2026-09-04：完成 2.1~2.3（入库三段：加载→切分→FAISS 持久化）
- 2026-09-06：完成 2.4~2.6（retriever 封装 + chain 问答链路 + FastAPI 问答接口）

## 本日做了什么

把 Step 1 的"手写文档 → 内存建库"升级成真实入库链路：TXT 文档加载 → 文本切分 → 自定义嵌入类正式化 → 项目路径基准 → FAISS 本地持久化；随后在 store 之上封装了正式的检索器（2.4），再把四个正式模块串成一条完整问答链 ask()（2.5），最后套上 FastAPI 的 HTTP 壳让前端能调（2.6）。最终效果：**源文档落盘后建库一次，浏览器 POST 一个问题就拿到严格基于资料的回答；库外的问题（闭包/GIL）模型会老实说"不知道"**。

## 目录结构（当前 rag 模块）

```
backend/app/rag/
├── __init__.py
├── loader.py     # load_txt()：TXT → Document 列表
├── splitter.py   # split_docs()：Document → 小 chunk
├── embedder.py   # SiliconFlowEmbeddings 类 + get_embedding() 工厂
├── prompts.py    # RAG_PROMPT（Step 1 写的）
├── store.py      # store_exists() / build_store() / load_store()
├── retriever.py  # retrieve()：问题 → 命中的前 k 块原文   ✅ 2.4
└── chain.py      # ask()：完整问答链路                   ✅ 2.5
config.py 新增：PROJECT_ROOT / DATA_DIR / FAISS_INDEX_DIR

backend/app/ 接口层（FastAPI，Step 1 已建 main.py）
├── main.py           # /health + include_router 挂问答路由
├── routers/chat.py   # POST /api/v1/chat 接口函数       ✅ 2.6
└── schemas/chat.py   # ChatRequest / ChatResponse 模型   ✅ 2.6
```

## 执行的关键代码/命令

| 代码/命令 | 解释 |
|-----------|------|
| `cd backend && ../venv/Scripts/python.exe -m app.rag.embedder` | 验证自定义嵌入类正式化后仍可用 |
| `python -m app.config` | 验证路径基准常量指向正确 |
| `python -m app.rag.store` | 完整链路：加载→切分→建库→存盘→读盘→检索 |
| `python -c "..."`（tempfile 临时目录） | 验证 faiss 在英文路径可保存，锁定中文路径根因 |
| `python -m app.rag.retriever` | 2.4：检索器运行，命中装饰器主题 |
| 改名 `project2` → `project2_bak` 再跑 | 2.4：故意制造"库不存在"，验证防御报错生效 |
| `python -m app.rag.chain` | 2.5：链路自测——装饰器题答对；闭包/GIL 等库外题答"不知道" |
| `..\venv\Scripts\python.exe -m uvicorn app.main:app --reload` | 2.6：启动接口服务，浏览器开 /docs 交互测试 POST /api/v1/chat |

注意运行方式：**`python -m` 从 backend 目录执行**，模块名用点分路径、不带 `.py`。

## 核心代码段

### 1. TXT 加载（`app/rag/loader.py`）

```python
from langchain_community.document_loaders import TextLoader

def load_txt(path: str) -> list:
    loader = TextLoader(path, encoding="utf-8")
    return loader.load()   # 1 个 TXT → 1 个 Document，metadata 自动带 source
```

### 2. 文本切分（`app/rag/splitter.py`）

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_docs(docs, chunk_size=200, chunk_overlap=20):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)
```

样例文档（6 个 Python 知识点主题）默认参数切成 **11 段**。

### 3. 自定义嵌入正式化（`app/rag/embedder.py`）

把 Step 1 测试脚本里的类搬进正式模块 + 工厂函数，配置从 `config.py` 读：

```python
from langchain_core.embeddings import Embeddings
from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBEDDING_MODEL

class SiliconFlowEmbeddings(Embeddings):
    def __init__(self, api_key, base_url, model):
        self.api_key, self.base_url, self.model = api_key, base_url, model

    def embed_documents(self, texts):      # 批量：列表进 → 向量列表出
        resp = requests.post(f"{self.base_url}/embeddings",
                             headers={"Authorization": f"Bearer {self.api_key}",
                                      "Content-Type": "application/json"},
                             json={"model": self.model, "input": texts})
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    def embed_query(self, text):           # 单个：问题 → 向量
        return self.embed_documents([text])[0]

def get_embedding():
    """工厂：屏蔽"从哪读配置"，调用方拿到的就是配好参数的对象"""
    return SiliconFlowEmbeddings(SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBEDDING_MODEL)
```

关键点：**配置和代码分离**——base_url/model 只存在于 config.py 一处，改配置不用动逻辑代码。

### 4. 路径基准（`app/config.py` 追加）

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # config.py 在 backend/app/，上跳 2 级 = 项目根
DATA_DIR = PROJECT_ROOT / "data"
# faiss 的 C++ 层在 Windows 打不开中文路径 → 索引放用户主目录的英文路径
FAISS_INDEX_DIR = Path.home() / "faiss_index" / "project2"
```

**为什么需要**：相对路径 `"data/..."` 依赖"当前在哪个目录运行"，而 `import app.xxx` 又要求从 backend 运行，两难。用 `__file__` 定位的绝对路径不受运行目录影响。

### 5. FAISS 持久化（`app/rag/store.py`）

```python
from langchain_community.vectorstores import FAISS
from app.config import FAISS_INDEX_DIR
from app.rag.embedder import get_embedding

def store_exists() -> bool:
    return (FAISS_INDEX_DIR / "index.faiss").exists()

def build_store(docs) -> FAISS:
    embeddings = get_embedding()
    vectorstore = FAISS.from_documents(docs, embeddings)
    FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)   # 目录缺哪层建哪层，存在就跳过
    vectorstore.save_local(str(FAISS_INDEX_DIR))          # 落盘：index.faiss + index.pkl
    return vectorstore

def load_store() -> FAISS:
    embeddings = get_embedding()
    # allow_dangerous_deserialization：pkl 用 pickle 反序列化，langchain 默认拒绝，
    # 只有加载自己生成的、可信的索引才显式放行
    return FAISS.load_local(str(FAISS_INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
```

启动时判断分支：`store_exists()` 为真走 `load_store()`（快，日常路径）；否则 `build_store(chunks)`（慢，仅首次/文档更新时）。

### 6. 检索器（`app/rag/retriever.py`）✅ 2.4

在 store 之上封装"问题 → 相关块"：

```python
"""检索器：给定问题，从已建好的向量库里取回最相关的 k 块文本"""
from app.config import RETRIEVER_TOP_K
from app.rag.store import store_exists, load_store

def retrieve(question: str, k: int = RETRIEVER_TOP_K) -> list[str]:
    """把用户问题转成检索，返回命中的前 k 块原文。"""
    # 卫语句：前置条件不满足，当场报清楚的中文错，不往下走
    if not store_exists():
        raise ValueError("向量库不存在，请在 backend 目录先运行：python -m app.rag.store")

    vectorstore = load_store()                        # 走到这 = 库一定就绪
    docs = vectorstore.similarity_search(question, k=k)  # 返回 Document 对象列表
    return [doc.page_content for doc in docs]          # 只要原文，转 list[str]

if __name__ == "__main__":
    results = retrieve("怎么给函数加额外功能？", k=2)
    for result in results:
        print(result)
        print("=" * 50)
```

**为什么在 vectorstore 外面再包一层**：
1. 职责分层——store 管"怎么建库/读盘"（基础设施），retriever 管"问题→相关块"（业务动作）
2. 解耦——将来换存储后端或检索策略，只动 retriever 内部，上层 chain/接口一行不改
3. 统一入口——2.5 的 chain、2.6 的 FastAPI 只认 `retrieve(question)`

### 7. 问答链（`app/rag/chain.py`）✅ 2.5

```python
"""RAG 问答链：检索 → 拼上下文 → 填模板 → 调 LLM，一次 ask 完成问答"""
from app.config import RETRIEVER_TOP_K
from app.rag.retriever import retrieve
from app.rag.prompts import RAG_PROMPT
from app.utils.llm import call_llm

def ask(question: str, k: int = RETRIEVER_TOP_K) -> str:
    chunks = retrieve(question, k=k)              # ① 检索：相关块的 list[str]
    context = "\n\n".join(chunks)                 # ② 拼 context
    msg_objs = RAG_PROMPT.format_messages(context=context, question=question)  # ③ 填模板
    messages = [{"role": "user" if m.type == "human" else m.type, "content": m.content}
                for m in msg_objs]                # ④ human→user + 转 dict
    return call_llm(messages)                     #    调 LLM
```

关键点：**chain 只编排、不重写逻辑**——②③④ 和 Step 1 test_rag.py 的 ask() 相同，唯一区别是 ① 换成正式 `retrieve()`（test_rag 是内存现建库 + 手写 4 段文档）。迁移验证过的原型时只换组件来源，逻辑别动。
类型陷阱：retrieve() 已返回 `list[str]`（纯文本），若照抄 test_rag 的 `[doc.page_content for doc in docs]` 会 AttributeError——test_rag 里 `similarity_search` 返回 Document 对象，正式链这层已经把 `.page_content` 提取做掉了。

### 8. 问答接口（`schemas/chat.py` + `routers/chat.py` + `main.py`）✅ 2.6

```python
# schemas/chat.py —— 请求/响应模型（数据形状）
from pydantic import BaseModel
class ChatRequest(BaseModel):
    question: str
class ChatResponse(BaseModel):
    answer: str

# routers/chat.py —— 接口函数（只收参数、调 ask、返回，不写 RAG 逻辑）
from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.rag.chain import ask
router = APIRouter(prefix="/chat", tags=["问答"])     # 相对路径，前缀 main 里统一加
@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    answer = ask(req.question)
    return ChatResponse(answer=answer)

# main.py —— 入口，挂路由
from app.routers import chat
app.include_router(chat.router, prefix=API_V1_PREFIX)   # 最终 = POST /api/v1/chat
```

关键点：
- **三层分工**：schemas = 数据形状（Pydantic 校验）、routers = 接口动作、rag/ = 业务逻辑。router 里唯一的"业务动作"就是 `ask(req.question)` 一行——以后 RAG 内部随便改，router 一行不动（和 retriever 之于 store 同一套分层逻辑）。
- **FastAPI 自动 /docs**：不用手写接口文档，浏览器开 `/docs` 就能点按钮交互测每个接口。
- **CORS 中间件**（Step 1 已加）就是让 Vue3 前端跨域调这个接口用的，到 Step 3 会体现。

## 犯的错 & 解决方法

| 错误信息 | 原因 | 解决方式 |
|---------|------|---------|
| `ModuleNotFoundError: No module named 'config'` | 用 `from config import ...`，但 config.py 在 app 包里，全名是 `app.config` | import 用完整包路径：`from app.config import ...` |
| `Error while finding module specification for 'app.config.py'` | `python -m` 后面写了 `.py` 后缀 | 模块名不带 `.py`：`python -m app.config` |
| faiss `'f' failed: could not open ...\index.faiss for writing: No such file or directory` | 项目路径含中文，faiss（C++）用 fopen 按 ANSI 解析打不开 UTF-8 路径 | 索引目录放到纯英文路径（`Path.home()`），详见 error-log |
| `'mv' 不是内部或外部命令` | 在 Windows cmd 里敲了 Linux 命令 `mv`，cmd 没有它 | 改名用资源管理器右键，或 cmd 的 `ren`；`mv` 只在 git bash 里可用（2.4） |
| 测试防御分支时"找不到 project2 文件夹" | 在项目目录里找，但库在用户主目录 `C:\Users\PlusLcn\faiss_index\project2`（2.3 中文路径坑的延续） | 直接 `explorer C:\Users\PlusLcn\faiss_index`（2.4） |
| `TypeError: APIRouter.__init__() takes 1 positional argument but 2 were given` | 骨架占位 `APIRouter(...)` 里的 `...` 不是占位符，是 Ellipsis 对象，被当**位置参数**传进构造器；APIRouter 参数全是 keyword-only | 关键字填：`APIRouter(prefix="/chat", tags=["问答"])`（2.6） |
| `'APIRouter' object has no attribute 'router'`（预期） | `import router as chat_router` 后变量本身就是 router 对象，再 `.router` 找不存在的属性 | 用 `from app.routers import chat` + `chat.router`（2.6） |
| 浏览器开 `GET /` → 404 | 根路径没定义接口，FastAPI 只认声明过的路由 | 开 /docs 或 /api/v1/health；**404 ≠ 服务挂了**（2.6） |
| uvicorn 进程还在但 `ERR_CONNECTION_REFUSED` | 进程活着 ≠ 服务活着；或浏览器端口和 uvicorn 实际监听不一致 | 看启动时 `Uvicorn running on http://127.0.0.1:XXXX` 那行用真实地址（2.6） |

完整细节见 [error-log.md](error-log.md)。

## 本日知识点归纳

- **loader / splitter / store 是数据入库三段**：读原文 → 切小块 → 向量化持久化，各管一段、互不掺和
- **配置与代码分离**：embedder 不自己拼 base_url/model，从 config.py 读；工厂函数 `get_embedding()` 屏蔽构造细节
- **`__file__` + `parents[n]`**：从当前文件向上数 n 级得绝对路径，根治"相对路径随运行目录漂移"
- **FAISS 落盘 = 两个文件**：`index.faiss`（向量）+ `index.pkl`（原文/元数据/pickle 序列化）
- **索引是可重建的缓存**：源文档还在就能重建，不是资产 → 不必进项目目录/git
- **pickle 反序列化风险**：能执行文件里藏的代码 → langchain 强制 `allow_dangerous_deserialization=True` 显式确认
- **`mkdir(parents=True, exist_ok=True)`**：目录缺哪层建哪层；已存在不报错（否则抛 FileExistsError）。mkdir 只管建目录，不管存文件
- **Windows + C 原生库的中文路径坑**：Python 走宽字符接口没问题，faiss 这类 C 库按 ANSI 解析路径会炸
- **`import` 即执行**：import 一个模块会从上到下执行它的顶层代码（config 的 `load_dotenv()` 因此全项目只需触发一次）
- **retriever 是"业务动作"层**：store 管"怎么存/读"，retriever 管"怎么查"，上层只认 `retrieve(question)`（2.4）
- **返回值取舍**：`similarity_search` 返回 Document（含 metadata），但要拼 prompt 只要文本 → 返回 `list[str]`，需要来源信息时再升级（2.4）
- **卫语句（guard clause）**：入口先挡非法情况，不满足就 `raise` 当场中断；`raise` 后面的代码不执行，所以主逻辑不用套 `else`（2.4）
- **防御式编程**：函数的隐藏前提（store 必须先建好）要主动检查，报错文案写清楚"在哪跑什么命令"（2.4）
- **切分边界开始影响检索质量**：块内会混进邻主题标题（检索命中但带噪音），是后面优化切分的动机（2.4 观察）

- **chain 是编排层不是逻辑层**：ask() 不发明新算法，把 retrieve/prompt/llm 按顺序拼起来；②③④ 沿用 Step 1 验证过的写法，只换组件来源（2.5）
- **接口层 router 只做"翻译"**：HTTP 请求体 → ask() 参数 → HTTP 响应体，RAG 逻辑一行不写；改业务不动 router（2.6）
- **schemas/routers 是 FastAPI 的分层**：schemas 定义数据形状（Pydantic 校验），routers 定义接口动作，main.py 只组装 app + 挂路由（2.6）
- **检索没有"都不相关"的判定**：similarity_search 永远返回 top-k，问题再离谱也硬给 k 块——"你好"被塞生成器/with 相关块的根源（2.6 实测）
- **"资料没有就说不知道"约束有弹性**：对正经知识问题（闭包/GIL）模型老实说不知道；对闲聊"你好"会绕开约束打太极——约束管得住"硬编知识"，管不住"闲聊兜底"（2.6 实测）
- **`...`（Ellipsis）是真实对象，不是占位符**：`APIRouter(...)` = `APIRouter(Ellipsis)`，Ellipsis 会被当真参数传进函数（2.6）
- **keyword-only 参数**：函数签名 `*` 之后的参数必须按关键字传；FastAPI 的 APIRouter/FastAPI 构造参数大多如此（2.6）
- **进程活着 ≠ 服务活着**：uvicorn 崩退出后终端窗口还在；排查先看启动打印的监听地址和端口（2.6）

## 面试常见问题

Q: FAISS 为什么要本地保存/加载？
A: 建库要调嵌入 API 逐段算向量，很贵；保存后重启直接读盘，只有文档更新时才重建。

Q: build_store 和 load_store 各自什么时候调用？
A: build 是低频重活（首次/文档变更），load 是每次启动的日常路径，用 store_exists() 判断走哪条。

Q: load_local 为什么要 allow_dangerous_deserialization=True？
A: .pkl 是 pickle 反序列化，加载不可信文件可能执行恶意代码。langchain 默认拒绝，只对可信的自建索引显式放行。

Q: 相对路径有什么问题？怎么解决？
A: 相对路径的结果取决于进程"当前目录"，换个地方运行就找不到文件。用 `Path(__file__)` 从文件自身定位项目根，拼绝对路径。

Q: loader 读中文路径文件没问题，为什么 faiss 存索引就报错？
A: TextLoader 走 Python 的宽字符文件接口，支持中文；faiss 是 C++ 库，用 fopen 按系统 ANSI 代码页解析路径，中文 UTF-8 字节对不上就报错。

Q: retrieve 为什么要在 vectorstore 外面再包一层？（2.4）
A: ① 职责分层：store 管存储、retriever 管检索业务；② 解耦：换存储/检索策略只动 retriever；③ 统一入口：chain 和接口只认 retrieve(question)。

Q: 卫语句是什么？为什么 raise 后面不用写 else？（2.4）
A: 函数入口先检查前置条件，不满足就 raise 当场中断。因为 raise 会立刻终止函数，False 分支到不了 else，主逻辑不缩进更清爽。

Q: retrieve 为什么返回 list[str] 而不是 Document？（2.4）
A: 上层拼 prompt 只需要文本。Document 多带 metadata（来源等），等接口要展示出处时再加不迟——不为用不上的信息复杂化。

Q: chain 为什么不是直接把 test_rag.py 的 ask() 复制过来？（2.5）
A: ②③④ 逻辑确实相同，但要换组件来源：① 从"内存现建库 + 手写文档"换成正式 `retrieve()`（读盘库）。test_rag 是验证用的一次性脚本，chain 是生产入口，两者组件来源不同。

Q: router 里为什么不写 RAG 逻辑？（2.6）
A: 职责分层。router 只做 HTTP ↔ Python 的翻译：收参数、调 ask、包响应。RAG 逻辑都在 rag/ 模块，将来换检索/加流式只动 chain 或下层，接口和前端一行不改。

Q: POST /api/v1/chat 这个完整路径是怎么拼出来的？（2.6）
A: router 声明相对 prefix="/chat"，main.py 里 include_router 时统一加 prefix=API_V1_PREFIX（/api/v1）。全局前缀集中在入口管理，各 router 不感知。

## 练习题

2.3 收尾练习：
1. 手动删掉 `C:\Users\PlusLcn\faiss_index\project2` 整个目录，再跑一次 `python -m app.rag.store`，观察发生了什么，解释为什么
2. 把主流程改成真正的判断分支：`if store_exists(): vs = load_store() else: vs = build_store(chunks)`，跑两次验证第二次不重建（打印区分）
3. 把 `split_docs` 的 `chunk_size` 换成 config 里的 `CHUNK_SIZE`，对比块数变化并解释
4. 给样例 TXT 末尾加一段新主题，重新 build 后检索它，验证更新流程
5. 在 `docs/error-log.md` 补一条今天遇到的坑（格式照抄已有条目）

2.4 练习：
1. 换几个主题各问一句（"生成器怎么省内存？" / "列表推导式和 lambda 什么区别？"），观察 retrieve 是否命中对应主题
2. 把 k 改成 1 和 5 各跑一次，对比返回块数和内容，体会 top-k 的作用
3. 临时把 retrieve 改成返回 docs（Document 列表），在 `__main__` 里打印 `result.metadata` 看每个块的来源，再改回 list[str]
4. 默写一遍卫语句版 retrieve（不看文件），再对照——卫语句是高频面试手写题
5. 思考：retrieve 的报错信息为什么要把"在 backend 目录 + python -m app.rag.store"写全？省略后用户会卡在哪一步？

2.5 练习：
1. 把 ask 的 ② 故意改回 `[doc.page_content for doc in chunks]` 跑一次，看 AttributeError，理解 retrieve() 返回的已是纯文本
2. 给 ask() 加个 temperature 参数透传给 call_llm（沿用 config 默认），对比两次输出的差别，体会 LLM 非确定性
3. 问几个库里有的知识点，专挑相邻主题的题，观察命中噪音块时回答质量如何变化（呼应 2.4 的块边界现象）

2.6 练习：
1. ChatRequest 加一个可选字段 `k: int = None`：为 None 时 ask 用默认 top_k，给了就透传；用 /docs 分别测带 k 和不带 k
2. 在 ChatResponse 加 `sources: list[str]`：给 retrieve/ask 开个"返回带 metadata"的口子，把每块来源带出来——体会"等真要展示出处时再升级"（呼应 2.4 取舍）
3. 起服务后按 F12 看 Network 面板里 POST /api/v1/chat 的请求/响应 JSON 长啥样（面试被问"HTTP 层"时能答出实例）
4. 把 `GET /api/v1/health` 改成挂进一个带 tags 的 router 里，观察 /docs 分组变化

## 下一步做什么

Step 2 基础 RAG（2.1~2.6）已完成 ✅。下一步进**高级 RAG**：先做重排序（reranker）提升检索精度，顺带解决"闲聊被当检索、模型打太极"这类问题。PDF 加载 / 三种切分对比仍暂缓。