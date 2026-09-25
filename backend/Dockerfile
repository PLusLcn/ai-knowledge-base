# ============================================================
# 后端镜像（FastAPI + RAG）
# 构建上下文 = 项目根目录，不是 backend/
#   docker build -f backend/Dockerfile -t kb-backend .
#                                              ↑ 这个点 = 项目根
# ============================================================
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

# ------------------------------------------------------------
# ⭐ 为什么工作目录是 /app/backend 而不是 /app？
#
# config.py 里算数据目录用的是这行：
#     PROJECT_ROOT = Path(__file__).resolve().parents[2]
#
# 也就是说：代码文件的「第 3 层父目录」被当成项目根。
#   本机：项目二/backend/app/config.py → parents[2] = 项目二/  → 数据在 项目二/data  ✅
#   容器：/app/backend/app/config.py   → parents[2] = /app     → 数据在 /app/data     ✅
#
# 但如果写成 WORKDIR /app、代码放 /app/app/config.py：
#   /app/app/config.py → parents[2] = /      → 数据变成 /data   ❌ 全错
#
# 所以容器里【刻意保持和本机一样的层级】。这也顺带解决了 .env：
# load_dotenv() 是从当前目录往上找的，/app/backend 往上就是 /app，
# 和本机 backend/ 往上就是项目根，形状完全一致。
# ------------------------------------------------------------
WORKDIR /app/backend

# ① 先只 COPY 依赖清单 → 单独装依赖
#    这样只要 requirements.txt 没改，这一层就走缓存；
#    以后改代码不会重装一遍几百 MB 的依赖（镜像分层缓存）
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
        -i https://pypi.tuna.tsinghua.edu.cn/simple

# ② 再 COPY 代码 + 种子数据
#    只拷 app/ 这一个包：根目录那 8 个 test_*.py 互相 import、不可移植，不要
COPY backend/app/ /app/backend/app/
COPY data/ /app/data/

# ③ 索引目录用环境变量指定
#    本机靠 Path.home() 躲开中文路径；容器是 Linux，没这问题，直接放 /app 下好挂卷
ENV FAISS_INDEX_DIR=/app/faiss_index
RUN mkdir -p /app/faiss_index

EXPOSE 8000

# ⚠️ --host 0.0.0.0 必须有：容器里的 127.0.0.1 是【容器自己】的回环地址，
#    绑它的话，宿主机的端口映射会把请求送进来却没人接 → 外面永远访问不到
# ⚠️ 不加 --reload：那是开发用的，生产环境开着会多占一份文件监控
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
