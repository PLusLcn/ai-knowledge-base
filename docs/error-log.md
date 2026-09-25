# 错误日志 — AI知识库问答系统

## 2026-09-02

### 1. OpenAIEmbeddings 嵌入报 400

- **场景**：用 `langchain_openai.OpenAIEmbeddings` 调硅基流动嵌入 API
- **错误信息**：
  ```
  openai.BadRequestError: Error code: 400 - {'code': 20015, 'message': 'The parameter is invalid.'}
  ```
- **原因**：langchain-openai 默认用 tiktoken 把文本编码成 token 数字数组，再把数组作为 `input` 发送。OpenAI 官方支持这种输入，但硅基流动不支持。
- **解法**：写自定义 `SiliconFlowEmbeddings` 类（继承 `langchain_core.embeddings.Embeddings`），用 requests 直调 `/embeddings`，`input` 传文本字符串/列表。
- **预防**：兼容 OpenAI SDK 的服务不一定支持所有 OpenAI 特性；先裸调一次 HTTP 请求确认接口行为。

### 2. LLM 调用报 400（role 非法）

- **场景**：`call_llm` 调用 `/chat/completions`
- **错误信息**：
  ```
  requests.exceptions.HTTPError: 400 Client Error: Bad Request
  ```
- **原因**：`ChatPromptTemplate.format_messages()` 返回的消息对象 `.type` 是 `human`，API 只认 `system/user/assistant`。
- **解法**：转 dict 时映射 `human` → `user`：
  ```python
  {"role": "user" if m.type == "human" else m.type, "content": m.content}
  ```
- **预防**：凡是把 LangChain 消息转给非 OpenAI 的兼容接口，先确认 role 枚举。

## 2026-09-04

### 3. `from config import ...` 报 ModuleNotFoundError

- **场景**：`backend/app/rag/embedder.py` 顶部导入配置
- **错误信息**：
  ```
  ModuleNotFoundError: No module named 'config'
  ```
- **原因**：config.py 在 `app` 包里，模块全名是 `app.config`，不是顶层 `config`；import 的名字是包的完整路径。
- **解法**：
  ```python
  from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBEDDING_MODEL
  ```
  配套：必须在 backend 目录用 `python -m app.xxx` 运行（模块名点分、不带 `.py`），Python 才能定位到 `app` 包。
- **预防**：项目内跨模块引用统一写完整包路径；脚本运行入口统一从 backend 目录 `python -m`。

### 4. faiss 保存索引报错（Windows 中文路径）

- **场景**：`python -m app.rag.store` 建库后 `save_local()` 落盘
- **错误信息**：
  ```
  RuntimeError: ... faiss::FileIOWriter::FileIOWriter ... Error: 'f' failed:
  could not open C:\...\项目二\data\faiss_index\index.faiss for writing: No such file or directory
  ```
- **原因**：项目路径含中文。`mkdir`（Python）成功创建了目录，但 faiss 是 C++ 库，底层用 `fopen` 按系统 ANSI/GBK 代码页解析路径；Python 传给它的是 UTF-8 字节，对不上 → 报"目录不存在"。
- **解法**：索引这类 faiss 要读写的路径必须纯英文。放用户主目录：
  ```python
  FAISS_INDEX_DIR = Path.home() / "faiss_index" / "project2"
  ```
- **预防**：Windows 上凡是要交给 C/C++ 原生库（faiss、numpy 读某些格式等）的文件路径，避开中文；纯 Python 的 open（如 TextLoader 读源文档）不受影响。

## 2026-09-07

### 5. POST /api/v1/chat 报 500：answer 校验为 None

- **场景**：给 `ask()` 加 system_prompt 覆盖分支后，POST /api/v1/chat 正常问答
- **错误信息**：
  ```
  pydantic_core.ValidationError: 1 validation error for ChatResponse
  answer
    Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
  ```
- **原因**：`ask()` 的 `system_prompt=None` 分支（正常问答路径）构造完 `messages` 后**漏了 `return call_llm(messages)`**，函数走到末尾隐式返回 `None`。`answer = ask(...)` 拿到 None，`ChatResponse.answer` 声明为 str，Pydantic 校验当场失败 → 500。
- **解法**：漏 return 的分支补上 `return call_llm(messages)`。顺带教训：`__main__` 自测只测了带 system_prompt 的 else 分支，正常路径没测到才让这个 bug 溜过去——自测要覆盖每个分支。
- **预防**：函数里凡是有多分支，检查每个分支是否都有 return（没写 return 的函数一律返回 None）；None 不会报错，会一路穿透到接口层 Pydantic 校验才炸。

### 6. rerank 请求报错：字段/对象类型不对

- **场景**：写 `app/rag/reranker.py` 调硅基流动 `/rerank` 接口（对照 embedder 抄）
- **错误信息**：请求体字段不被识别 / 传入对象无法序列化 / 对返回值取属性报错
- **原因**：三处"照抄 embedder 没跟着改"：
  1. 请求体用 `"input"`（embedder 的字段），rerank 认 `"documents"`
  2. 把 `similarity_search` 返回的 `Document` 对象直接塞给 rerank——它只收纯文本 `list[str]`
  3. 把 `rerank()` 返回的 `(index, score)` 排序表当成重排好的文档继续 `.page_content`
- **解法**：
  ```python
  json={"model": self.model, "query": query, "documents": documents}  # 字段核对
  texts = [d.page_content for d in docs]      # 先抽纯文本
  ranked = reranker.rerank(question, texts)    # (原下标, 分数) 降序
  texts = [texts[i] for i, _ in ranked[:RERANK_TOP_K]]   # index 回查原文
  ```
- **预防**：调新端点时别只改 URL——把请求体字段名、接收的对象类型、返回结构的形状（是文档还是索引）一起对着文档核对。返回"排序表+下标"的接口，映射必须自己做。

## 2026-09-09

### 7. AttributeError: 'tuple' object has no attribute 'format_messages'

- **场景**：`prompts.py` 定义完 `HYDE_PROMPT`，`hyde.py` 里调 `HYDE_PROMPT.format_messages(...)`
- **错误信息**：
  ```
  AttributeError: 'tuple' object has no attribute 'format_messages'
  ```
- **原因**：定义模板结尾多写了一个逗号：
  ```python
  HYDE_PROMPT = ChatPromptTemplate.from_messages([...]),   # ← 行尾多一个逗号
  ```
  Python 里 `x = 表达式,` 会把右边**整体包成单元素元组**，所以 `HYDE_PROMPT` 变成 `(ChatPromptTemplate, )`，tuple 当然没有 `.format_messages()`。变量类型被"无声"改变，报错点（调用处）离真正原因（定义处行尾逗号）很远。
- **解法**：删掉行尾逗号。用 `type()` 确认：
  ```python
  from app.rag.prompts import HYDE_PROMPT
  print(type(HYDE_PROMPT))   # 应为 ChatPromptTemplate
  ```
- **预防**：Python 的尾随逗号在元组/多行列表里合法且常用，但**赋值语句**末尾的逗号会把值包成元组。定义完变量先 `print(type(...))` 确认类型，尤其是多行构造的对象。

### 8. 函数能跑但参数名拼错（use_hythesis）

- **场景**：`retriever.py` 给 `retrieve()` 加 HyDE 开关
- **错误信息**：无报错——函数跑通了
- **原因**：`hypothesis` 手误拼成 `hythesis`（漏 `p`），签名、判断、`__main__` 调用三处拼了同一个错名，所以"错得一致"、运行正常。这类错名以后极难读，也和 `hyde.py` 里规范的 `generate_hypothesis` 对不上。
- **解法**：统一改成 `use_hypothesis`，三处同步改。
- **预防**：写完新参数自查拼写；和项目里已有的规范命名对照（generate_hypothesis 拼对了，开关名就别另创一个拼错的）。

## 2026-09-16

### 9. 服务一启动就报 `Form data requires "python-multipart"`

- **场景**：给 `document.py` 写了 `file: UploadFile = File(...)`，准备启动 uvicorn 测试
- **错误信息**：
  ```
  RuntimeError: Form data requires "python-multipart" to be installed.
  You can install "python-multipart" with:
  pip install python-multipart
  ```
- **原因**：FastAPI 解析文件上传依赖 `python-multipart`，它是**硬依赖**（不是可选包）。注意报错时机——是**服务启动时**、在建立路由表解析函数签名的那一刻就炸，不是等收到上传请求才炸。所以现象是"服务根本起不来"，容易误以为是代码写错了。
- **解法**：`pip install python-multipart`，并把真实版本号写进 `requirements.txt`（写 `python-multipart==0.0.32`，别写 `0.0.*`）。
- **预防**：用到一个新框架特性时，先回头看它的依赖装全没有。报错信息里已经给了 pip 命令，照抄就行——**先读完报错再动手**，这次是在写代码之前就查了 requirements，省了一轮折腾。

### 10. 配置项写了但根本没起作用（CHUNK_SIZE 死配置）

- **场景**：`config.py` 声明了 `CHUNK_SIZE = 500` / `CHUNK_OVERLAP = 50`，建库时切块粒度却不是 500
- **错误信息**：无报错——库建出来了，检索也正常
- **原因**：`store.py` 的 `__main__` 调用的是 `split_docs(raw_docs)`，**没传 chunk_size / chunk_overlap**，于是走 splitter 的默认值 200/20。变量声明了却没人引用，成了死配置。
- **解法**：改成显式传参 `split_docs(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)`，重建后统一到 500/50（全量重建所以自洽）。
- **预防**：**配置中心里写的值必须真的被引用**，否则这个文件就是骗人的——后来人改它不会有任何效果，还会以为改生效了。定完配置项，回头搜一下有没有人读它。这类"不报错的错"比崩溃更难发现，只能靠主动核对。

## 2026-09-20

### 11. `python -m app.rag.store` 跑完"重建成功"，却把 uploads 的内容抹掉了

- **场景**：3.8 收口时跑 `python -m app.rag.store` 想重建知识库
- **错误信息**：无报错——打印"重建完成"，检索也正常
- **原因**：`store.py` 的 `__main__` 是从早期版本遗留下来的，只手写读了一个源文件：
  ```python
  raw_docs = load_txt("data/samples/python-basics.txt")
  chunks = split_docs(raw_docs)      # 还漏传了 chunk_size（同 #10）
  build_store(chunks)
  ```
  而 `build_store()` 内部是 `FAISS.from_documents()` + `save_local()`——**覆盖写**，不是追加。喂进去多少内容，磁盘索引就只剩多少内容，`data/uploads/` 里的东西全从索引里消失了。真正读两个目录的是 `rebuild_store()`。
- **解法**：`__main__` 改成调 `rebuild_store()`（全量：samples + uploads，分块参数走 config）。改完重跑 → `重建完成，共 6 块`（此前是 7，因为期间删掉了一个测试文件——顺带验证了"手动删除 + 重建"这条路是通的）。
- **预防**：**方法名是 build / create / from_xxx 的，默认当覆盖写处理**。覆盖写的东西，喂进去的范围必须**等于你想保留的全部范围**。只想加一点内容应该找 add 类接口，没有 add 就别用 build 硬塞。同族问题见 #10——都是"不报错的错"。

### 12. `requirements.txt` 里躺着 2~3GB 的无人依赖（sentence-transformers）

- **场景**：3.8 第 2 步依赖可复现性审计，逐个搜 `requirements.txt` 里的包在代码里被谁 import
- **错误信息**：无报错——本机装着，一切正常
- **原因**：`sentence-transformers` 写在清单里，但**全项目零引用**。嵌入走的是硅基流动 API（自己写的 `SiliconFlowEmbeddings`，requests 直调 `/embeddings`），根本没用本地模型。它自己会拖 `torch` + `transformers`，装完 2~3GB，全进 Docker 镜像。
- **解法**：从清单移到文件末尾的"当前不装"注释区，写明原因（要用再装）。**本机不用卸载**——venv 里已经装好，代码不 import 就不加载，照常能跑。`requirements.txt` 管的是"干净机器上 `pip install -r` 会装什么"，不是"本机装了什么"。
- **预防**：依赖清单要**从代码反查着写**，不能从教程/模板抄。审计动作很机械：对每个包名全局搜一次 import，搜不到就查它是不是别人的传递依赖（如 `httpx` 是 `openai` 带的）。另外注意——本次只验证到"没有代码引用它"，**没验证到"干净机器装得起来"**，后者要等 Docker 里真跑一次 `pip install -r` 才算数。

## 2026-09-25

### 13. nginx 拒绝启动：`host not found in upstream "backend"`

- **场景**：3.9 第 3 步，单独跑前端容器 `docker run -p 8081:80 kb-frontend`，想先看看静态页
- **错误信息**：
  ```
  2026/09/25 06:37:47 [emerg] 1#1: host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:39
  nginx: [emerg] host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:39
  ```
  容器 `Exited (1)`，**连首页都打不开**（`HTTP 000`）
- **我的预判错了**：我以为"静态文件能发，只有 `/api` 会 502"。实际是 nginx 直接不启动。
- **原因**：`proxy_pass http://backend:8000;` 里写的是**域名**。nginx 在**启动那一刻**就要把 upstream 的域名解析成 IP，解不出来就判定配置非法，整个进程断言失败退场。而此刻还没有 compose、没有 `backend` 这个主机名。
  - 对比 `vite.config.js` 里写的是 `target: 'http://127.0.0.1:8000'` —— **IP 不需要查 DNS**，所以后端没启动 Vite 也照样跑。**写 IP 和写域名的差别，就是在这里炸的。**
- **解法**：让 `proxy_pass` 里出现**变量**，nginx 就会把解析推迟到每次请求：
  ```nginx
  resolver 127.0.0.11 valid=10s ipv6=off;   # Docker 内置 DNS 的固定地址
  set $backend_upstream http://backend:8000;
  proxy_pass $backend_upstream;
  ```
  改完重跑 → 容器 Up，`/` 和 `/chat` 都是 200。
- **预防**：**nginx 的 upstream 主机名是"启动时解析"，不是"请求时解析"。** 想在服务不在时也能启动（这个特性在生产里很有用：后端挂了不该把前端一起带走），就必须用 `resolver` + 变量。另外这也是 `depends_on` 不能替代的东西——`depends_on` 只管启动顺序，不管"后端是否已经能服务"。

### 14. `docker compose up --build` 报 gRPC 头含非 ASCII 字符

- **场景**：3.9 第 4 步，写完 `docker-compose.yml` 第一次执行 `docker compose up -d --build`
- **错误信息**：
  ```
  #1 [internal] load local bake definitions
  #1 reading from stdin 1.08kB 0.0s done
  failed to dial gRPC: rpc error: code = Internal desc = rpc error: code = Internal
  desc = header key "x-docker-expose-session-sharedkey" contains value with
  non-printable ASCII characters
  ```
- **原因**：项目目录名是 **`项目二`（中文）**。compose 的构建走 **bake** 这条路径，bake 会拿构建路径派生一个 session key 放进 gRPC 头，中文让这个头变成非法值。**`docker build` 不走 bake，所以同样的项目手敲构建完全正常**——这也是为什么前面几次手敲构建从没报过。
- **解法（绕过）**：关掉 BuildKit，退回旧构建器
  ```bash
  DOCKER_BUILDKIT=0 docker compose up -d --build
  ```
  实测通过（输出 `Successfully tagged kb-frontend:latest`）。
  另外 `COMPOSE_BAKE=false` **无效**——试过，报一模一样的错。
- **预防**：Docker 工具链对非 ASCII 路径的支持是**分路径的**，有的地方好使有的地方炸。项目目录名（以及上级目录名，本例上级还有 `ai学习规划`）出现中文，就随时可能踩到。要么接受"改代码重建固定加 `DOCKER_BUILDKIT=0`"，要么把整条路径改成英文。

### 15. 卷挂上了，但索引是空的 → 问答 500

- **场景**：compose 起好后第一次提问
- **错误信息**：接口 HTTP 500，日志里：
  ```
  File "/app/backend/app/rag/retriever.py", line 12, in retrieve
      raise ValueError("向量库不存在，请在 backend 目录先运行：python -m app.rag.store")
  ValueError: 向量库不存在
  ```
- **原因**：`kb_index` 是个**全新**的命名卷，里面什么都没有。而镜像里的 `/app/faiss_index` 也是空的——Dockerfile 里只有 `RUN mkdir -p`，`data/faiss_index/` 又被 `.dockerignore` 排除了。**"持久化"和"有内容"是两件事**：卷保证了数据不丢，但首次创建时它本来就是空的。
  - 顺带：本机那个真正的索引在 `C:\Users\PlusLcn\faiss_index\project2`，从来没进过镜像，也不可能自动出现在卷里。
- **解法**：在容器里跑一次全量重建
  ```bash
  docker compose exec backend python -m app.rag.store
  ```
  → `重建完成，共 6 块`，问答恢复 200。
- **预防**：**新卷 = 空目录**，别指望它自动有数据。凡是"首次运行需要初始化数据"的服务，都要么在启动脚本里做幂等初始化（`if not store_exists(): rebuild_store()`），要么在 run-guide 里写清"第一次必须先跑这一条"。本例走的是后者——写进 run-guide。**这个 500 是设计使然，不是 bug。**

### 16. Git Bash 的两个坑（本机专属，反复踩）

- **① `/app` 被改写成 Windows 路径**
  ```
  $ docker exec kb-backend ls -a /app
  ls: cannot access 'C:/Program Files/Git/app': No such file or directory
  ```
  Git Bash 的 MSYS 路径转换看到 `/xxx` 就当 Unix 路径翻译成 Windows 路径。解法：命令前加 `export MSYS_NO_PATHCONV=1`。
  同类命令：`docker compose exec backend ls /app/faiss_index`、`rm -f /app/data/uploads/...`。
- **② 用 `curl -d` 传中文 JSON → 后端返回 400 `There was an error parsing the body`**
  Python 侧 schema 完全正确，是终端把中文按 GBK 编码塞进了请求体。解法：**别用 curl 测中文请求**，改用 Python（`urllib` / `httpx`）发，body 显式 `.encode('utf-8')`。
- **③ 控制台打印中文变乱码**（`������`）
  这只影响**显示**，不影响数据。判断依据：把响应写进 UTF-8 文件再打开看，内容完好。
- **预防**：Windows + Git Bash + 中文，这三个凑一起时，先怀疑**工具链的编码/路径转换**，再怀疑代码。另外别用 `netstat -ano | findstr :8000` 判断端口——它会匹配到 IPv6 地址里的 `:8000:` 子串，要认 `LISTENING` 那一列。
