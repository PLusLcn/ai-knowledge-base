# Day 8：文件上传——从浏览器到知识库重建

## 用时

- 2026-09-16：第 1、2 次（后端接收存盘 / 重建知识库）
- 2026-09-19：第 3、4 次（前端上传按钮 / 知识库文档列表）

> 计划里的 3.5~3.7。拆成 4 次做，理由是"合并成一次的话，出问题时你分不清是存盘错了还是建库错了"——每一步都能单独验证。

## 本日做了什么

| 任务 | 内容 | 状态 |
|------|------|------|
| 3.5 后端接收 + 存盘 | `POST /api/v1/documents/upload`，校验后缀 → 存进 `data/uploads/` | ✅ |
| 3.6 重建知识库 | `load_dir()` + `rebuild_store()`，上传后全量重建 FAISS | ✅ |
| 3.7 前端上传按钮 | `el-upload` + `:http-request` 自定义上传 + `api/document.js` | ✅ |
| 3.7 知识库文档列表 | `GET /documents` + `onMounted` 拉取 + `v-for` 渲染 | ✅ |
| 验证 | 青鸟实验：上传前问不出、上传后能答出 | ✅ |

## 涉及的文件

| 文件 | 作用 |
|------|------|
| `backend/app/routers/document.py` | **新建**：上传接口 + 文件列表接口 |
| `backend/app/rag/store.py` | 加 `rebuild_store()` |
| `backend/app/rag/loader.py` | 加 `load_dir()` |
| `backend/app/config.py` | 加 `SAMPLES_DIR`、`UPLOAD_DIR` |
| `backend/app/main.py` | 注册 document 路由 |
| `backend/requirements.txt` | 加 `python-multipart==0.0.32` |
| `frontend/src/api/document.js` | **新建**：`uploadDocument()` + `listDocuments()` |
| `frontend/src/views/ChatView.vue` | 加 `el-upload` 按钮 + 文档列表 |

---

## 链路一：上传一个文件之后发生了什么（完整时序）

**这是本次最重要的一张图。** 前端 4 步，后端 6 步，然后原路返回。

```
【前端】
① 用户点"上传文档" → 弹文件选择框 → 选中 x.txt
      ↓
② el-upload 把文件打包成一个 File 对象
      ↓
③ 调 :http-request 指定的 customUpload(options)
      options.file 就是那个 File 对象
      ↓
④ uploadDocument(options.file)
      new FormData() → formData.append('file', file)
      POST /api/v1/documents/upload
      ↓
⑤ Vite 代理：路径以 /api 开头 → 转发到 127.0.0.1:8000

【后端】
⑥ main.py 的路由表把 /api/v1/documents/upload 交给 upload_document()
      ↓
⑦ 校验后缀（不是 .txt → 400）
      ↓
⑧ Path(file.filename).name  ← 丢掉路径，防路径穿越
      ↓
⑨ await file.read() 拿字节 → write_bytes 存进 data/uploads/x.txt
      ↓   ★ 到这里文件已经落盘，前端那一层完全不知道
⑩ rebuild_store()
      load_dir(samples) + load_dir(uploads)
      → split_docs(chunk_size=500, chunk_overlap=50)
      → build_store() → FAISS.from_documents() → save_local() 覆盖磁盘索引
      ↓
⑪ vectorstore.index.ntotal 数一下多少块

【返回】
⑫ {"filename", "size", "chunks", "message"}
      ↓
⑬ 回到前端 customUpload：ElMessage.success(data.message) 弹提示
      ↓
⑭ await loadDocuments() → GET /documents → documents.value = [...]
      ↓
⑮ Vue 响应式察觉数组变了 → 重绘列表
```

**数据在哪一层：**

| 步骤 | 数据住在哪 |
|---|---|
| ④ 之前的 File 对象 | 浏览器内存 |
| ⑨ 之后 | 后端磁盘 `data/uploads/` |
| ⑩ 之后 | FAISS 索引文件（`Path.home()/faiss_index/project2`） |
| ⑭ 之后 | 前端内存（`documents` 这个 ref） |

---

## 链路二：页面打开时列表怎么来的

```
浏览器打开 localhost:5173
  → ChatView.vue 创建
  → onMounted(loadDocuments) 触发
  → listDocuments() → GET /api/v1/documents
  → 后端 list_documents() 遍历 samples + uploads 两个目录
  → {"files": ["python-basics.txt", "test_upload.txt", ...]}
  → documents.value = res.data.files
  → Vue 重绘 → 列表出现
```

**关键：列表以后端为准，前端不自己记。** 所以刷新页面列表还在，和后端磁盘永远一致。

---

## 本日知识点

### ⭐ 一、FastAPI 怎么收文件

```python
@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
```

- `UploadFile` 是**类型**，`File(...)` 是**标记**，告诉 FastAPI"这个参数从 multipart 表单里取"
- 对比之前 `ChatRequest`（Pydantic 模型）：那是 JSON body，靠请求体解析；这是表单，靠 multipart 解析
- `...` 是 Python 的 `Ellipsis`，表示"必填"

**硬依赖**：`python-multipart` 不装，服务**启动就崩**：

```
RuntimeError: Form data requires "python-multipart" to be installed.
```

注意是**启动时**报，不是请求时才报——FastAPI 在建立路由表时就要解析 `File(...)` 签名。

### ⭐ 二、路径穿越防御

```python
filename = Path(file.filename).name
```

`file.filename` 是**攻击者可控**的。如果他传 `../../../../Windows/System32/x.txt`，直接拼进 `UPLOAD_DIR / filename` 就会写到系统目录外面去。

`Path(...).name` 只取最后一段，把 `../` 全部丢掉。

**同类规则**：凡是外部传进来的、要拼进文件路径的字符串，一律先取 basename。

### ⭐ 三、`load_dir()` 三个细节

```python
def load_dir(dir_path: str) -> list:
    docs = []
    for path in sorted(Path(dir_path).glob("*.txt")):
        docs.extend(load_txt(str(path)))
    return docs
```

- `glob("*.txt")` 返回**生成器**，不是列表
- `sorted(...)` 保证顺序稳定——文件系统返回的顺序不保证，能跑一次的代码不算好代码，能稳定复现的才算
- `extend` 不是 `append`：`append` 会把整个列表当成**一个元素**塞进去，变成嵌套列表

### ⭐ 四、上传后不用重启服务（核心认知）

`retrieve()` 每次请求都调 `load_store()` **现读磁盘**。上传接口已经 `save_local()` 覆盖了磁盘索引，所以下一个请求读到的就是新库。

| 写法 | 上传后要不要重启 |
|---|---|
| 每次请求 `load_store()` 现读 | **不用**（本项目） |
| 启动时 `@app.on_event("startup")` 加载进全局变量 | 要 |

**权衡**：现读的代价是每次请求多一次磁盘 IO；缓存进内存快，但改完索引必须重启，而且多进程部署时（uvicorn 多 worker）各进程各缓存一份，更难同步。

### 五、`vectorstore.index.ntotal`

FAISS 底层对象上直接能读，等于索引里的向量总数 = 切出来的块数。用它可以不查库就报出"共 N 块"。

### 六、`async def` 里别直接调同步阻塞函数

```python
vectorstore = rebuild_store()          # ← 会卡住事件循环
await run_in_threadpool(rebuild_store) # ← 正解
```

`rebuild_store()` 是同步阻塞的（要调嵌入 API、算向量），在 `async def` 里直接调会**堵住整个事件循环**，期间其他请求全部排队。当前是单人开发自测，没改；上线前要处理。

对照：`list_documents()` 用的是普通 `def`，FastAPI 会自动把它丢进线程池，不占事件循环。

### ⭐ 七、前端传文件：FormData

```js
const formData = new FormData()
formData.append('file', file)
const res = await request.post('/documents/upload', formData)
```

- `append` 的**第一个参数是字段名**，必须和后端 `File(...)` 的参数名一致。不一致 → **422**（不是 400）
- **不要手写 `Content-Type`**。浏览器发 multipart 时会自动补上 `multipart/form-data; boundary=xxxx`，后端靠这串随机 boundary 拆分字段。手写就把 boundary 弄丢了

### ⭐ 八、`el-upload` 的 `:http-request`

```html
<el-upload action="#" accept=".txt" :show-file-list="false" :http-request="customUpload">
  <el-button :loading="uploading">上传文档</el-button>
</el-upload>
```

`el-upload` 自带上传功能（内部自己发请求），但那样不走我们的 axios，`baseURL` 和超时都套不上。`:http-request` 把它**整个换掉**：组件只负责弹文件框、把文件接住，发请求交给我们自己的函数。

- `action="#"` 是它设计上必须有个提交地址，走自定义上传时用不到
- `accept=".txt"` **只是文件选择框的过滤条件，不是安全措施**——用户切成"所有文件"照样能选别的。真正拦住非 txt 的是后端那句 `HTTPException(400)`

**前端过滤是体验，后端校验才是防线。**

### ⭐ 九、Vue：`ref` 和 `.value`

```js
const documents = ref([])
```

`ref()` 是个**包装盒**。`documents` 是盒子，数组在盒子里。

```js
documents.value = ['a.txt']   // 改盒子里的 value → Vue 察觉 → 重绘 ✅
documents.value.push('b.txt') // 同理 ✅
documents = ['a.txt']         // 把盒子扔掉换个新的 → Vue 盯的还是旧盒子 ❌
```

**判断标准不是"push 还是整体赋值"，是有没有通过 `.value` 碰那个盒子。**

**例外**：模板里不写 `.value`。

```html
{{ documents.length }}    <!-- 模板里 Vue 自动拆盒 -->
```
```js
documents.value.length    <!-- JS 里必须自己拆 -->
```

模板是 Vue 的地盘，它帮你拆；JS 是你自己的地盘，自己拆。

### ⭐ 十、Vue：谁调用，谁给参数

```js
sendQuestion(question)          // ChatView 调 → question 由 ChatView 给
customUpload(options)           // el-upload 调 → options 由 el-upload 给
onMounted(loadDocuments)        // Vue 调 → 无参
```

**传函数本身（不带括号）** = 交给别人调；**带括号** = 立刻执行、把返回值传过去。

所以 `onMounted(loadDocuments)` 对，`onMounted(loadDocuments())` 错。同理 `:http-request="customUpload"` 对，`:http-request="customUpload()"` 错。

这也是"`api/` 目录下的函数看着参数悬空"的答案——它们都是**定义在这里、等别人来调用**的半成品。

### 十一、Vue：`onMounted` 生命周期

组件从创建到销毁有一串固定时机，`onMounted` 是其中一个：**组件的 DOM 已经真正放进页面了**。页面一打开就拉数据，标准位置就是这里。

### 十二、Vue：`v-for` 和 `:key`

```html
<div v-for="doc in documents" :key="doc"> {{ doc }} </div>
```

`:key` 是给每一项的**身份证**，Vue 更新列表时靠它判断"这一项还是不是原来那一项"。

**不要用下标当 key**：删掉第 1 项后，原来第 2 项的下标从 1 变成 0，Vue 以为"下标 0 那项还在、只是内容变了"，于是复用原来的 DOM。列表项里如果有输入框、勾选框这类自身状态，状态会串到别的项上。

配套的 `v-if="documents.length"`：条件为假时整个元素**不渲染**（不是隐藏），用来在列表为空时把带边框的盒子整个去掉。

---

## ⭐ 怎么验证 RAG 真的生效（本次最值钱的一课）

第一次验证是失败的：上传了 GIL 的内容，然后问"什么是 GIL"，答得挺好——**但这证明不了任何事**。

因为 DeepSeek-V3 自己就知道 GIL。**检索一块都没命中的话，它照样答得出来。**

**正确做法：上传 LLM 不可能知道的内容，也就是你编的。**

1. 先问：`项目二的内部代号是什么？` → 答不出（或编一个）
2. 上传一个自己编的 txt：

```
项目二的内部代号是"青鸟"。
青鸟计划由三人小组在 2026 年 9 月启动，目标是把内部 FAQ 文档做成问答接口。
```

3. 再问同一个问题 → 答出"青鸟"，才说明检索真的生效

**顺带认识幻觉**：第 1 步它要是真编了个代号，那就是 RAG 的幻觉问题——检索不到时 LLM 不会说"我不知道"，而是编一个像样的答案。RAGAS 的 Faithfulness 指标量的就是这个。

**当前接口的一个局限**：`ChatResponse` 只有 `answer` 一个字段，命中的原文（citation）没返回，前端看不到"这条答案是根据哪几块生成的"。真实产品都会列出"参考文档 1/2/3"。加这个不难，在本项目的砍单里，先记着。

---

## 面试常见问题

1. **FastAPI 里接收文件上传和接收 JSON 有什么区别？**
   JSON 用 Pydantic 模型声明参数，靠请求体解析；文件用 `file: UploadFile = File(...)`，靠 multipart 表单解析，且必须装 `python-multipart`，否则服务启动就报错。

2. **用户上传的文件名能直接用吗？**
   不能。`file.filename` 是客户端可控的，可能含 `../` 造成路径穿越。要先 `Path(file.filename).name` 只取文件名。同理，后缀校验必须在后端做，前端的 `accept` 只是选择框过滤。

3. **用户上传文档后，问答服务需要重启吗？**
   取决于检索侧怎么拿 vectorstore。本项目 `retrieve()` 每次请求都 `load_store()` 现读磁盘，上传接口已经覆盖了磁盘索引，所以不用重启。如果启动时把索引加载进全局变量，就必须重启，而且多 worker 部署时每个进程各有一份缓存，更难同步。

4. **`async def` 里调用耗时的同步函数会怎样？**
   会阻塞事件循环，期间所有请求排队。要用 `run_in_threadpool` 或者 `asyncio.to_thread` 丢到线程池。反过来，普通的 `def` 端点 FastAPI 会自动丢线程池，不占事件循环。

5. **前端怎么把文件发给后端？为什么不能手动设 `Content-Type`？**
   `FormData` + `append(字段名, file)`，字段名要和后端参数名一致。multipart 请求需要一个随机 boundary 来分隔字段，浏览器会自动生成并写进 `Content-Type`；手写这行会覆盖掉它，boundary 丢失，后端解析不出文件。

6. **`el-upload` 的 `:http-request` 是干什么的？**
   覆盖组件自带的上传实现。默认它内部自己发请求，不走项目的 axios 实例（baseURL、拦截器、超时都套不上）；用 `:http-request` 指定自己的函数，组件只负责选文件和接住文件。

7. **Vue 里改数据为什么有时界面不更新？**
   最常见的原因是把 ref 变量本身重新赋值（`documents = [...]`），而不是改它的 `.value`。Vue 追踪的是 ref 对象的属性变化，整个换掉对象，它盯的还是旧的。

---

## 踩的坑

| 现象 | 原因 | 解法 |
|------|------|------|
| 服务**一启动**就报 `RuntimeError: Form data requires "python-multipart"` | 没装 `python-multipart`，FastAPI 解析 `File(...)` 签名时就要用 | `pip install python-multipart`，并写进 requirements.txt（写死真实版本号） |
| 上传接口返回 **422** 而不是 400 | `formData.append` 的字段名和后端 `File(...)` 的参数名对不上 | 两边都叫 `file` |
| 上传成功、能答出来，但不确定检索是否真生效 | LLM 自身就知道答案，检索全不命中也能答 | 用编造内容测（见上面"怎么验证 RAG 真的生效"） |
| 文档列表刷新页面就空了、知识库里已有的文件不显示 | 列表当时只是个前端内存数组，靠上传时 push，从没问过后端 | 改成 `GET /documents` + `onMounted` 拉取，列表以后端为准 |
| 传非 txt 文件，前端没拦住 | `accept=".txt"` 只是选择框过滤，用户能切成"所有文件" | 后端 `HTTPException(400)` 才是真正的防线 |

### 顺带修正的一处旧隐患

`config.py` 里的 `CHUNK_SIZE=500` / `CHUNK_OVERLAP=50` 原本是**死配置**——`store.py` 的 `__main__` 调用 `split_docs(raw_docs)` 没传参，用的是 splitter 的默认值 200/20，所以旧索引是按 200/20 建的。

本次改成显式传参，**重建后分块粒度 200 → 500**（全量重建所以自洽）。若日后检索效果变差，先回看这里。

---

## 3.8 收口验收（2026-09-20 补记）

### 第 1 步：冷启动，把顺序固定下来

```
① 两个终端全关（Ctrl+C）—— 先确认端口真的空了
      ↓           netstat -ano | findstr :8000
② 起后端
      ↓           ← 后端启动时就会暴露"路由表 / 依赖"级别的错
      ↓             （python-multipart 那次就是在这里炸的，不是收到请求才炸）
③ 地址栏输入 /api/v1/health
      ↓           ← 这一步只验"后端活着"，和前端无关
④ 起前端
      ↓
⑤ 浏览器操作页面
                  ← 这一步才验"前端能不能摸到后端"
```

**为什么必须这个顺序**：先起前端的话，报错只有"接口连不上"一种说法，分不清是后端没起、还是后端起来了但崩了。拆成 ③ 单独验，一次只怀疑一个东西。

> `--reload` 模式下 uvicorn 有**父进程 + 子进程**。只关一个窗口端口不释放，下次启动报 `10048`。

### 两个"看着有问题、其实没问题"的现象

**① 打开 `127.0.0.1:8000` 得到 `{"detail":"Not Found"}`**

不是坏了。`main.py` 里**没有 `@app.get("/")`**，根路径本来就没东西。

完整路径是**两层前缀拼出来的**：

| 层级 | 来源 | 贡献 |
|---|---|---|
| 1 | `main.py` 的 `include_router(document.router, prefix=API_V1_PREFIX)` | `/api/v1` |
| 2 | `document.py` 的 `APIRouter(prefix="/documents")` | `/documents` |

拼出来 `/api/v1/documents`。**地址栏不会帮你补前缀**，少一段就是 404。

**② "上传新文件之后回答变慢了"**

量完发现是假的。同一句话问 3 次，耗时上下跳——那是 LLM 生成的正常波动。

| 阶段 | 上传后会变吗 | 量级 |
|---|---|---|
| `load_store()` 读磁盘 | 索引 24KB → 28KB | 毫秒级 |
| `similarity_search` 相似度计算 | 6 个向量 → 7 个 | 微秒级 |
| prompt 拼装 | k=5 固定 | 基本不变 |
| **DeepSeek-V3 生成** | **完全无关** | **秒级 —— 占 99%** |

**测法**：F12 → Network → 点 `chat` 那条请求 → Timing → 看 "Waiting for server response"，同一句话跑 3 次。别靠感觉。

### 自己撞出来的真问题：删掉源文件，为什么还能答出来

先把两个存储位置摆清楚：

```
data/samples/*.txt  +  data/uploads/*.txt        ← 源文件（人能直接看见的）
                    │
                    │  只有 rebuild_store() 被调用时，这条线才走一次
                    ↓
        ~/faiss_index/project2/index.faiss       ← 检索真正读的地方
                    │
                    │  retrieve() 每次请求都读它
                    ↓
                  LLM 生成答案
```

关键事实：**`rebuild_store()` 全项目只有一个调用点——上传接口。**

| 你干了什么 | 索引跟着变吗 |
|---|---|
| 通过页面上传 | ✅ 上传接口内部调了 `rebuild_store()` |
| 在资源管理器里手动删/丢文件 | ❌ **没有任何人重建** |

所以"上传后不用重启服务"这句话的真相不是"索引跟着源目录走"，而是"**上传那条路恰好顺手重建了索引**"。

**同一对矛盾的第二处**：文档列表是 `glob` **直接读目录**的，检索是**读 faiss** 的。两个数据源。于是删掉的文件从列表里消失了，但问它照样答得出来——**界面和现实不一致**。

**处理决定：不加删除接口、不加"重建"按钮。**

理由：真正的解法是**增量索引**（FAISS 支持 `add` / `delete` 单个向量），全量重建只是把补丁换个位置。这个决定写进 README 的「已知限制」，把时间留给 Docker。已同步到 `run-guide.md` 第 3 节，下次遇到直接查，不用再当 bug 查一遍。

### 第 2 步：依赖可复现性审计（写 Dockerfile 之前必须做）

**为什么顺序不能反**：Docker ≈ 在**一台干净机器上从零装依赖**。不先审计，Docker 一报错你分不清是 Dockerfile 写错了，还是清单本来就是不全的。

审计方法很机械：对着 `requirements.txt` **逐个包名全局搜 import**。

| 包 | 情况 | 处理 |
|---|---|---|
| `sentence-transformers` | **全项目零引用**（嵌入走 API，不用本地模型），却拖来 `torch` + `transformers` | 移出清单，省 2~3GB 镜像 |
| `httpx` | 代码没直接用，但 `openai` SDK 依赖它，装了也会被带进来 | 留着，加注释说明（冗余，不算错） |
| `rerankers` | 从来没装过、也不需要——`reranker.py` 用 `requests` 直调 `/rerank` | 旧注释写错了，改正 |
| `fastapi-cors` | 不需要——`CORSMiddleware` 是 FastAPI 内置的 | 同上，注释改正 |

**顺带查出来的四件事（都是 3.9 的伏笔）：**

1. **`app/` 是自包含的** —— 没有任何 `app/` 下的文件 import 根目录那 8 个 `test_*.py`。所以 **Docker 镜像只需要 `app/` + `requirements.txt`**。
2. **那 8 个根目录脚本互相 import**（`test_faiss.py` → `from test_embedding_custom import SiliconFlowEmbeddings`），这个依赖只在 cwd = `backend/` 时成立 → **不可移植，别往镜像里塞**。
3. **根目录那个 88 字节的 `package-lock.json` 是误在项目根跑 npm 留下的**，已删。`npm ci` 只认**和 `package.json` 同目录**的锁文件，留着会误导 Dockerfile 的 COPY 路径。
4. ⚠️ **`.env` 在项目根，不在 `backend/` 里。** 现在能跑是因为 `load_dotenv()` 会**从当前目录往上找**。Docker 里 `WORKDIR /app` 只 COPY backend 的内容 → 找不到 → `SILICONFLOW_API_KEY = None` → **import 时不报错，第一次调 API 才 401**。这是 3.9 要处理的第一件事。

### 一个诚实的边界

删掉 `sentence-transformers` 那行，**只验证到"没有代码引用它"，没验证到"干净机器上装得起来"**。后者要等真的在干净环境跑一次 `pip install -r requirements.txt` 才算数——那正好就是 3.9 Docker 要做的事。到时候它是第一个被检验的。

---

## 3.9 Docker 容器化部署（2026-09-25 补记）

### 四个必须先立的心理模型

Docker 全是"看不见的机制"，光看指令记不住。真正接上的是这四句类比：

| 概念 | 类比 | 为什么这个类比成立 |
|---|---|---|
| **镜像 / 容器** | 安装光盘 / 装好的机器 | 镜像是只读模板，容器 = 镜像 + 一个可写层。一台机器装坏了，重装一遍就是；光盘本身永远不变 |
| **Dockerfile** | 刻光盘的配方 | 它是"怎么做这张光盘"的说明书，本身不是光盘 |
| **镜像分层 + 缓存** | 叠盘子，改底下的上面全得重摆 | 某层的输入没变就能复用；一旦某层变了，**叠在它上面的每一层全部失效** |
| **构建期 / 运行期** | 装机时 / 用机时 | `CMD` 在 build 期间**根本不会被执行**，它只是在运行时被记录下来 |

**⭐ 最容易卡住的是最后一条。** 把"构建期 / 运行期"分开之后，一大半 Docker 的疑问会自动消解（为什么 `COPY` 之后代码才生效？为什么改环境变量要重新 run？）。

### 分层缓存：用数字砸实（实测）

同一个前端镜像，第一次构建 vs 改了 `nginx.conf` 后重建：

| 层 | 命令 | 首次 | 改了 nginx.conf 后 |
|---|---|---|---|
| 基础镜像 | `FROM node:22-alpine` | 拉取 | `CACHED` |
| 装依赖 | `RUN npm ci` | **1分35秒** | `CACHED`（不动） |
| 拷源码 | `COPY frontend/ ./` | — | 失效（nginx.conf 在这个目录里） |
| 编译 | `RUN npm run build` | — | 重跑 2.6s |
| 拷产物 | `COPY --from=build /build/dist` | — | 重跑 |
| 拷配置 | `COPY frontend/nginx.conf` | — | 重跑 |
| **合计** | | **1分35秒** | **7秒** |

**结论**：`nginx.conf` 在盘子最上面，所以它一变，只有它上面那两层要重摆；底下 1GB 的 node 阶段和 239 秒的 `npm ci` 一动不动。

**推论（这才是要背下来的）**：Dockerfile 里的指令顺序不是随意的 ——
> **慢且不常变的放下面，快且常变的放上面。**

所以两个 Dockerfile 都是「先 COPY 依赖清单 → 装依赖 → 再 COPY 源码」。反过来写的话，改一行 Python 就要重装一遍几百 MB 的依赖。

### 多阶段构建：盖房子

前端需要 Node 才能**编译**，但编译产物跑起来**完全不需要 Node**。

```
   阶段 1（node，~1GB）              阶段 2（nginx，52MB）
   脚手架 + 工人 + 搅拌机    ──→    只留房子
   npm ci / npm run build          nginx + dist(1.45MB)
        ↓ 产出 dist/
   交完钥匙整个拆掉
```

关键就一行：`COPY --from=build /build/dist /usr/share/nginx/html`。

**实测结果**：最终镜像 **95.4MB**，进去 `which node` → 不存在。阶段 1 的一切（node、npm、源码、node_modules）都不在最终镜像里。

对比：**后端镜像 620MB**（单阶段）。前端用多阶段，省掉了整整一个运行时。

### 三层容器架构

```
   浏览器 → http://127.0.0.1:8081
              ↓
   ┌──────────────────────────────────┐
   │ kb-frontend  (nginx :80)          │   无卷
   │   /      → dist/ 静态文件         │
   │   /api/  → http://backend:8000    │
   └───────────────┬──────────────────┘
                   ↓  kb_kb-net（Docker 内部 DNS）
   ┌──────────────────────────────────┐
   │ kb-backend   (uvicorn :8000)      │   kb_kb_data  → /app/data
   │                                   │   kb_kb_index → /app/faiss_index
   └───────────────┬──────────────────┘
                   ↓
          api.siliconflow.cn（外部服务）
```

**"为什么 docker 里不放前端"是个误会** —— 前端进了 Docker，只是在**另一个容器**里。

**前端源码一个字都没改**，因为 `chat.js` / `document.js` 里写的是：

```js
baseURL: '/api/v1',     // 相对路径 = "跟当前页面同一个地址"
```

页面从哪来，请求就往哪发。所以：

| | 开发时 | 生产（Docker）时 |
|---|---|---|
| 页面谁给的 | Vite 开发服务器 :5173 | nginx 容器 :80 |
| `/api/v1/...` 谁转发 | `vite.config.js` 的 `server.proxy` | **nginx** 的 `location /api/` |
| 前端代码 | `baseURL: '/api/v1'` | **同一行，没动** |

**换掉的是执行者，不是代码。** 这就是为什么 `vite.config.js` 里那段 proxy，在 Docker 里要用 nginx 重新实现一遍。

### 保留目录深度：一个必须想清楚的设计

`config.py` 里：

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

这个 `parents[2]` 硬编码了**目录深度**。所以容器里必须复现本机的层级：

| 容器里代码放哪 | `parents[2]` 是什么 | 数据落到哪 | |
|---|---|---|---|
| `/app/backend/app/config.py` | `/app` | `/app/data` | ✅ |
| `/app/app/config.py`（压平） | `/` | `/data` | ❌ 全错 |

所以 `WORKDIR` 写成 `/app/backend` 而不是 `/app`。

**顺带解决了两件事**：
1. 数据目录自动落对位置
2. `.env` 的坑消失 —— `load_dotenv()` 从当前目录**往上找**，`/app/backend` 往上就是 `/app`，和本机 `backend/` 往上就是项目根，形状完全一致

> 这就是"**硬编码相对层级**"这种写法的代价：它把目录结构变成了**接口**，搬家时必须原样复刻。如果当初写成 `Path.home() / "..."` 或环境变量，就没这个约束。**记下来：能靠环境变量配置的路径，不要靠目录层级推导。**

### 构建上下文 & `.dockerignore`

**构建上下文 = 发给 Docker 守护进程的那一坨文件**，由 `docker build` 最后那个 `.` 指定。

- 本项目必须用**项目根**做上下文，因为 `data/` 和 `backend/` 是**同级目录**，而**上下文之外的文件 COPY 不进来**
- `.dockerignore` 管的是「**哪些文件发给守护进程**」，**不是**「哪些文件进镜像」——后者是 COPY 决定的。这个区分是第一大混淆点

**实测**：本机 `frontend/node_modules` 是 **136MB**，实际发出的上下文只有 **1.12MB** —— `.dockerignore` 里写 `node_modules/` 就能挡住 `frontend/node_modules/` 这种嵌套路径，不用写 `**/node_modules/`。

`.dockerignore` 最要紧的一条是 **`.env` 排除** —— 密钥绝不进镜像。

### 🔑 `.env` 在运行期是怎么被读出来的（本次重点）

先分清两件事：

```
   .env 文件  ≠  环境变量
   （磁盘上的一行文本）   （某个进程内存里的一块数据）
```

完整链路：

```
① .env 躺在宿主机磁盘上：SILICONFLOW_API_KEY=sk-xxxx
      ↓
② 你敲 docker compose up（或 --env-file .env）
   执行的是【宿主上的 Docker CLI】
      ↓
③ CLI 打开 .env，逐行解析成 key=value
      ↓
④ CLI 把键值对随"创建容器"请求发给守护进程
      ↓
⑤ 守护进程启动容器主进程（PID 1，即 uvicorn）时，
   把它写进【这个进程的环境变量表】
      ↓
⑥ ⭐ 到这里 .env 文件退场，值变成"进程内存里的数据"
      ↓
⑦ Python 解释器由 uvicorn 启动，继承同一张表
      ↓
⑧ os.getenv("SILICONFLOW_API_KEY") 读的就是这张表
```

**三层验证（实测，三个视角读同一个值）**：

| 层 | 命令 | 读到 |
|---|---|---|
| ① Docker 的记录 | `docker inspect ... --format '{{range .Config.Env}}...'` | ✅（**容器没运行也能读**，因为是元数据） |
| ② 进程自己（和 `config.py` 同一条路） | `docker exec ... python -c "os.getenv(...)"` | ✅ |
| ③ 内核暴露的 PID 1 内存区 | `cat /proc/1/environ` | ✅ |

**三条硬证据**：

1. **容器里根本没有 `.env` 文件**（`find / -name ".env"` 空），但 `os.getenv` 读得到 → 文件可以不存在，值依然在
2. **`TZ` / `FAISS_INDEX_DIR` 也在 `/proc/1/environ` 里** —— 它们来自 Dockerfile 的 `ENV` 指令，不是 `.env` 文件。**两种来源汇进同一张表**，进程眼里没有区别
3. **容器一停，②③ 就跑不了**（没有进程就没有环境变量表），但 ① 还能跑 → **"环境变量"本质是"属于某个进程的内存"**

**安全习惯**：`docker inspect` 会**明文**打印密钥，而它的输出经常进 CI 日志、截图、剪贴板。所以读密钥一律只印前 4 位：

```bash
docker inspect kb-backend --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed 's/\(SILICONFLOW_API_KEY=.\{4\}\).*/\1****/'
```

### 本步实测结果汇总

| 验收项 | 结果 |
|---|---|
| 后端构建 | `pip install` 层 **249.9 秒**；`Successfully installed` 列表里**没有 torch / transformers / sentence-transformers** |
| 后端镜像体积 | **620MB**（若含 `sentence-transformers` 会到 2.5~3GB） |
| 前端镜像体积 | **95.4MB**，最终镜像里 `node` 不存在 |
| 前端构建 | 首次 1分35秒 → 只改 `nginx.conf` 后 **7 秒** |
| 容器内 `PROJECT_ROOT` | `/app`（`DATA_DIR=/app/data`、`FAISS_INDEX_DIR=/app/faiss_index`）—— 设计意图验证通过 |
| 容器内 `.env` | **不存在**，但 KEY 读得到（长度 51） |
| `docker inspect` 里两种来源 | `SILICONFLOW_API_KEY`（--env-file）与 `TZ`/`FAISS_INDEX_DIR`（Dockerfile ENV）在同一张表 |
| `/api/v1/health` 经 nginx | HTTP 200（容器间 DNS 解析成功） |
| `POST /chat`（装饰器） | HTTP 200，**6.2s**，答案来自索引内容 |
| `POST /documents/upload` | HTTP 200，块数 **6 → 7** |
| `docker compose down` → `up` | `index.faiss` 原样还在，问答照常 |

> **⭐ 3.8 那个依赖审计在这里拿到了首次真实验证**：`pip install` 的安装列表里确实没有 `sentence-transformers` 及其拖油瓶 `torch`/`transformers`，镜像只有 620MB 而不是 2.5GB+。此前只验证到"没有代码引用它"，现在验证到了"干净机器装得起来"。

### 本次踩的 4 个新坑（详见 `error-log.md` #13~#16）

| # | 坑 | 一句话教训 |
|---|---|---|
| 13 | nginx 拒绝启动 `host not found in upstream "backend"` | **nginx 解析 upstream 域名是在启动那一刻，不是请求时**。写 IP 不查 DNS 所以没事，写域名就会炸 |
| 14 | `docker compose up --build` 报 non-printable ASCII | 目录名 `项目二` 是中文，compose 的 bake 构建路径派生 session key 时炸了。加 `DOCKER_BUILDKIT=0` 绕过 |
| 15 | 卷挂上了但索引是空的，问答 500 | **"持久化"和"有内容"是两件事**。新卷就是空目录，首次要手动初始化 |
| 16 | Git Bash 路径改写 + curl 传中文 400 + 控制台乱码 | Windows + Git Bash + 中文凑一起时，**先怀疑工具链的编码/路径转换，再怀疑代码** |

### 本步新增文件

| 文件 | 作用 |
|---|---|
| `backend/Dockerfile` | 后端镜像（单阶段） |
| `frontend/Dockerfile` | 前端镜像（**多阶段**：node 编译 → nginx） |
| `frontend/nginx.conf` | 发静态文件 + 反向代理 `/api` |
| `docker-compose.yml`（项目根） | 一条命令编排两个服务 + 卷 + 网络 |
| `.dockerignore`（项目根） | 过滤构建上下文（含 `.env`，密钥不进镜像） |

修改：`backend/app/config.py` —— `FAISS_INDEX_DIR` 改成可用环境变量覆盖（**本机不设该变量，行为完全不变**）。

---

## 下一步

- **3.8 第 3 步**：`docs/run-guide.md`（启动命令清单 + 排错决策树）—— ✅ 已写，2026-09-20
- **3.9 Docker + docker-compose 部署** —— ✅ 已完成，2026-09-25（详见上一节）
  **三个提前挖出来的坑，全部命中并已处理：**
  1. ✅ **`.env` 在项目根** → 用 `WORKDIR /app/backend` 保持层级 + compose `env_file` 注入解决
  2. ✅ **`sentence-transformers` 已从清单移除** → `pip install` 安装列表里确认没有 torch/transformers，镜像 620MB 而非 2.5GB+，**首次拿到真实验证**
  3. ✅ **`npm ci` 用 `frontend/` 自己的锁文件** → Dockerfile 里 `COPY frontend/package.json frontend/package-lock.json ./`
  - ✅ **FAISS 索引**：用 `FAISS_INDEX_DIR` 环境变量覆盖成 `/app/faiss_index`，再由 compose 卷持久化（首次需手动跑一次 `docker compose exec backend python -m app.rag.store`）
- **3.10 README + 项目截图**。
- **README 必须写进去的「已知限制」**：索引与源目录不同步（手动删文件后，列表里消失但问答仍答得出）。原因见上面"自己撞出来的真问题"。
- 遗留优化点（已告知、未改）：
  - `async def` 里同步阻塞的 `rebuild_store()` → `await run_in_threadpool(rebuild_store)`
  - `loader.py` 的 `__main__` 和 `test_splitter.py` 里还写着相对路径 `"data/samples/..."`，只在 cwd 是 `backend/` 时能跑
  - 问答接口不返回 citation
  - 想做增量索引（FAISS `add` / `delete`）替代全量重建——这才是"删文件不同步"的真正解法
