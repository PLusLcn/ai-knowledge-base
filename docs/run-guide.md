# 运行手册（run-guide）

> 用途：① 从零把项目跑起来 ② 出问题先查这里，别瞎改代码
> 最后更新：2026-09-25

**两种跑法，别混：**
- **本机开发** → 看第 1 节（两个终端，改代码热更新）
- **Docker 部署**（一条命令拉起前后端）→ 直接跳到**第 5 节**

---

## 0. 路径地图

先认清东西放在哪，一半的"灵异问题"都是找错文件。

| 东西 | 真实位置 | 说明 |
|---|---|---|
| 后端代码 | `项目二/backend/app/` | 自包含，不依赖 backend 根目录那 8 个 `test_*.py` |
| 前端代码 | `项目二/frontend/src/` | |
| **API Key** | `项目二/.env`（项目根，**不在 backend 里**） | `load_dotenv()` 从当前目录往上找，所以在 backend 里跑也能找到 |
| 源文档 | `项目二/data/samples/` + `项目二/data/uploads/` | 放 txt 的地方 |
| **真正在用的索引** | `C:\Users\PlusLcn\faiss_index\project2\` | `index.faiss` + `index.pkl` |
| 项目内那个 `data/faiss_index/` | **空的** | 历史遗留。当初想放项目里，但 faiss 是 C++ 写的，**打不开含中文的路径**，所以改到用户目录了 |
| Python 环境 | `项目二/venv/` | |

---

## 1. 本机开发方式启动（严格按这个顺序）

顺序不是讲究，是**为了出错时能分清是哪一段坏了**。先起前端的话，报错只会告诉你"接口连不上"，看不出是后端没起还是后端起崩了。

### 1.1 先起后端

```bash
cd backend
../venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 才算起来了。**别关这个终端**。

### 1.2 浏览器验活（这一步不许跳过）

地址栏输入**完整路径**：

```
http://127.0.0.1:8000/api/v1/health
```

期望：`{"status":"ok","message":"服务运行正常"}`

> ⚠️ 只输 `127.0.0.1:8000` 会得到 `{"detail":"Not Found"}` —— 这不是坏了。`main.py` 里**没有 `@app.get("/")`**，所以根路径没东西。
> 完整路径是**两层前缀拼出来的**：`/api/v1` 来自 `main.py` 的 `include_router(..., prefix=API_V1_PREFIX)`，`/api/v1/health` 再拼上路由自己声明的路径。地址栏不会帮你自动补前缀。

### 1.3 再起前端

```bash
cd frontend
npm run dev
```

浏览器打开终端里打印的地址（默认 `http://localhost:5173`）。

> Vite 发现 5173 被占会自动顺延到 5174/5175，**这不是错误**。代理照样打到 8000，不影响使用。

### 1.4 关掉

两个终端各按 `Ctrl + C`。

> `--reload` 模式下 uvicorn 有**父进程 + 子进程**两个。只关一个窗口可能端口没释放，下次启动报 `10048`。
> 确认端口真的空了：
> ```bash
> netstat -ano | findstr :8000
> ```
> ⚠️ **这个命令会误报。** `findstr :8000` 是纯文本匹配，IPv6 地址里就含 `:8000:` 这个子串（比如 `...:8000:0:b00:105`），看着像有输出其实端口是空的。**只认 `LISTENING` 那一列**——没有 `LISTENING` 行就是真的空。
> 确实被占用就用 `taskkill /PID <最后一列的PID> /F` 杀掉。

---

## 2. 排错决策树

**先定位坏在哪一层，再动手。** 90% 的时间浪费在改错地方。

### 第一步：F12 → Network 面板

| 现象 | 坏在哪 | 去看 |
|---|---|---|
| Network 里**根本没有**那条请求 | **前端** | 按钮的 `@click` 绑上了吗？函数真的被调到了吗？在函数第一行 `console.log` 一下 |
| 请求是**红的**，状态 404 | **路由对不上** | 见下面「404 三查」 |
| 状态 **422** | **字段对不上** | FastAPI 校验失败，Response 里会写明缺哪个字段。拿它和 `app/routers/` 里 Pydantic 模型的字段名逐字对比 |
| 状态 **500** | **后端业务段** | 看后端终端里的 traceback。常见：`向量库不存在`、嵌入模型/LLM 调用失败 |
| 转圈很久最后成功 | **正常** | LLM 生成要几秒，99% 的耗时在这 |

### 「404 三查」（按顺序查）

1. **路径前缀写全了吗** —— `/api/v1` 是 `main.py` 加的，`/documents` 是路由文件加的，浏览器和 axios 都**不会自动补**
2. **代理配了吗** —— 前端只用相对路径（`/api/v1/documents`），靠 `vite.config.js` 里的 `proxy` 转发到 8000。写死 `http://127.0.0.1:8000` 就绕过了代理（本项目开了 CORS 所以也能通，但换个环境就挂）
3. **改完代理重启了吗** —— `vite.config.js` 的改动**不会热更新**，必须重启 `npm run dev`

### 提示"上传成功"但**检索不到新内容**

不是前端的问题，也不是 LLM 的问题。查这两条：

1. `data/uploads/` 里**文件真的在吗**（上传接口是先落盘再重建，中间失败会提示报错）
2. 索引进去了吗 —— 看后端终端，上传成功会打印重建日志；再不行用下面第 3 节手动重建一次

---

## 3. 知识库重建

### 什么时候需要重建

| 你干了什么 | 索引跟着变吗 |
|---|---|
| 通过**页面上传**文件 | ✅ 自动重建（上传接口内部会调 `rebuild_store()`） |
| **手动**往 `data/samples/` 或 `data/uploads/` 里丢/删文件 | ❌ **不会**。必须手动重建 |
| 改了 `CHUNK_SIZE` / `CHUNK_OVERLAP` | ❌ 不会，必须手动重建 |

### 怎么重建

```bash
cd backend
../venv/Scripts/python.exe -m app.rag.store
```

它会全量读 `samples/` + `uploads/` 两个目录，重新分块、重新建索引，然后读回来做一次检索自测。看到「重建完成，共 N 块」+ 打印出内容 = 成功。

### ⚠️ 已知限制（别踩）

- **删源文件不会自动同步索引。** 你在资源管理器里删掉一个 txt，`GET /documents` 的列表里它会消失（列表是直接读目录），但**问答仍然答得出来**（检索只读 faiss 索引）。这不是 bug，是没做增量索引 —— 见 README「已知限制」。
- **`build_store()` 是覆盖写**，不是追加。所以 `store.py` 的 `__main__` 里**不要**只手写某个源文件喂给它，那样会把 `uploads/` 的内容整个从索引里抹掉。

---

## 4. 一句话速查

```bash
# 后端
cd backend && ../venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# 验活
http://127.0.0.1:8000/api/v1/health

# 前端
cd frontend && npm run dev

# 重建索引
cd backend && ../venv/Scripts/python.exe -m app.rag.store

# 端口占用
netstat -ano | findstr :8000

# ---------- Docker 方式（见第 5 节）----------
cd 项目二 && docker compose up -d                    # 启动
cd 项目二 && DOCKER_BUILDKIT=0 docker compose up -d --build   # 改了代码后重建再启动
cd 项目二 && docker compose down                     # 停掉（卷保留）
cd 项目二 && docker compose logs -f backend          # 看日志
```

---

## 5. Docker 方式启动（一条命令拉起前后端）

### 5.1 两条命令跑起来

```bash
cd "C:/Users/PlusLcn/Desktop/python/ai学习规划/项目二"

docker compose up -d                    # 首次会构建镜像，要几分钟
```

然后浏览器打开 **http://127.0.0.1:8081**。

> **为什么是 8081 不是 8080？** 8080 被项目一的 `blog-backend` 占了。

### 5.2 改代码之后怎么办

| 你改了什么 | 要做什么 |
|---|---|
| `backend/app/` 里的 Python 代码 | `DOCKER_BUILDKIT=0 docker compose up -d --build` |
| `frontend/src/` 里的 Vue 代码 | 同上 |
| `docker-compose.yml` | 同上 |
| 什么都没改，只是重启电脑后想跑 | `docker compose up -d` 就够（不用 `--build`） |

> ⚠️ **`--build` 前面那个 `DOCKER_BUILDKIT=0` 不能省。** 你的项目目录名是 `项目二`（中文），compose 走 bake 构建时会拿路径派生 session key，非 ASCII 字符会让它报
> `header key "x-docker-expose-session-sharedkey" contains value with non-printable ASCII characters`。
> 加 `DOCKER_BUILDKIT=0` 退回旧构建器就没事了。详见 `error-log.md` #14。
> 注意：**手敲 `docker build` 不受影响**，只有 compose 的构建路径有这个毛病。

### 5.3 首次启动必须先做一次：建索引

**新卷是空的。** `docker compose up` 起来后直接提问会得到 **HTTP 500**，日志里写：

```
ValueError: 向量库不存在，请在 backend 目录先运行：python -m app.rag.store
```

执行一次（只需要第一次）：

```bash
docker compose exec backend python -m app.rag.store
```

看到「重建完成，共 N 块」就行。之后索引存在 `kb_kb_index` 卷里，`docker compose down` 再 `up` 也不会丢。

> 这不是 bug。持久化和"有内容"是两件事：卷保证了数据不丢，但它刚创建时本来就是空的。
> 本机那个索引在 `C:\Users\PlusLcn\faiss_index\project2`，从来没进过镜像，也不会自动出现在卷里。

### 5.4 容器结构

```
   浏览器 → http://127.0.0.1:8081
              ↓
   ┌──────────────────────────────────┐
   │ kb-frontend  (nginx, 容器内 :80)  │
   │   /       → /usr/share/nginx/html │  ← 前端构建产物 dist
   │   /api/   → http://backend:8000   │  ← 反向代理（替代 Vite 的开发代理）
   └───────────────┬──────────────────┘
                   ↓  kb_kb-net 内部网络，靠服务名寻址
   ┌──────────────────────────────────┐
   │ kb-backend   (uvicorn, :8000)    │
   └───────────────┬──────────────────┘
                   ↓
          api.siliconflow.cn
```

| 卷 / 网络 | 挂到哪 | 作用 |
|---|---|---|
| `kb_kb_data` | `/app/data` | 源文档（samples + uploads） |
| `kb_kb_index` | `/app/faiss_index` | FAISS 索引 |
| `kb_kb-net` | — | 两个容器的内部网络，`backend` 这个名字靠它解析 |

> **⚠️ 两个卷必须一起持久化。** 只留索引不留源文件 → 就是那个"删了文件还能回答"的问题（见第 3 节）。只留源文件不留索引 → 每次都得重算 embedding，慢。

### 5.5 Docker 方式排错

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `docker compose up --build` 报 `non-printable ASCII` | 中文目录名 | 命令前加 `DOCKER_BUILDKIT=0` |
| 页面打不开，`docker compose ps` 显示 frontend 在重启 | nginx 配置错 | `docker compose logs frontend` |
| 页面能开，但所有 `/api` 请求 **502** | backend 没起来 / 起来了但崩了 | `docker compose ps` + `docker compose logs backend` |
| 问答 **500**，日志 `向量库不存在` | 新卷是空的 | 跑一次 5.3 那条 `exec` |
| 问答 **500**，日志提到 401 / API key | `.env` 没找到 | 确认项目根有 `.env`，且 `docker-compose.yml` 里有 `env_file: .env` |
| 上传成功但检索不到 | 同第 3 节的已知限制 | — |
| 想进容器里看看 | — | `docker compose exec backend sh`（退出用 `exit`）<br>⚠️ Git Bash 里先 `export MSYS_NO_PATHCONV=1`，否则 `/app` 这类路径会被改写成 Windows 路径 |

### 5.6 彻底清空（连数据一起删）

```bash
docker compose down -v          # -v = 连卷一起删，上传的文档和索引全没
docker rmi kb-backend kb-frontend
```

⚠️ `-v` 是不可逆的，上传的文档会真的消失。平时停止用 `docker compose down`（不带 `-v`）就够了。
