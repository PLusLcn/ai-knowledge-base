import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # 加载项目根目录的 .env 文件

# 硅基流动配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# 模型配置
LLM_MODEL = "deepseek-ai/DeepSeek-V3"
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# LLM 参数
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 2048

# 检索参数
RETRIEVER_TOP_K = 5        # 初检索取数量
RERANK_TOP_K = 3           # 重排序后保留数量
CHUNK_SIZE = 500           # 文本分割块大小
CHUNK_OVERLAP = 50         # 块重叠字符数

# FastAPI
API_V1_PREFIX = "/api/v1"

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # 先想：为什么是 [2]？
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"  
UPLOAD_DIR = DATA_DIR / "uploads"
# 为什么不用项目内路径：faiss C++ 打不开中文路径，所以本机放用户主目录。
# 容器里没有中文路径问题（Linux），用环境变量覆盖成 /app/faiss_index。
# 本机不设这个环境变量 → 行为和以前完全一样。
FAISS_INDEX_DIR = Path(os.getenv("FAISS_INDEX_DIR") or (Path.home() / "faiss_index" / "project2"))


if __name__ == "__main__":
    print(PROJECT_ROOT)
    print(FAISS_INDEX_DIR)
