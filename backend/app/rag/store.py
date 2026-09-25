from langchain_community.vectorstores import FAISS
from app.rag.embedder import get_embedding
from app.rag.loader import load_dir
from app.rag.splitter import split_docs
from app.config import FAISS_INDEX_DIR, SAMPLES_DIR, UPLOAD_DIR, CHUNK_SIZE, CHUNK_OVERLAP

# 状态查询（返回 True/False）
def store_exists() -> bool:
    # 返回 FAISS_INDEX_DIR / "index.faiss" 这个文件在不在（用 Path.exists()）
    # 用 os/pathlib 判断文件存在，你学过
    return (FAISS_INDEX_DIR / "index.faiss").exists()

#  写入（建库 + 存盘）
def build_store(docs) -> FAISS:
    # 1.拿嵌入对象
    embeddings = get_embedding()
    # 2.建索引 ← 你 Step1 test_faiss.py 里用过
    vectorstore = FAISS.from_documents(docs, embeddings)
    # 3. 目录不存在就自动创建
    FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    # 4.存盘
    vectorstore.save_local(str(FAISS_INDEX_DIR))
    # 5. return vectorstore
    return vectorstore

def rebuild_store() -> FAISS:
    """全量重建知识库：samples + uploads 两个目录里的所有 txt"""
    docs = load_dir(str(SAMPLES_DIR)) + load_dir(str(UPLOAD_DIR))
    chunks = split_docs(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return build_store(chunks)

# 读取（从磁盘读取（返回 vectorstore））
def load_store() -> FAISS:
    # 1. get_embedding()
    embeddings = get_embedding()
    # 2. FAISS.load_local(str(FAISS_INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
    vectorstore = FAISS.load_local(str(FAISS_INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
    # 3. return 读回来的 vectorstore
    return vectorstore

if __name__ == "__main__":
    # 重建知识库：samples + uploads 全量，分块参数走 config
    # ⚠️ 别在这里只手写某个源文件去 build_store()——那是覆盖写，
    #    只喂一个文件会把 uploads 里的内容整个从索引里抹掉
    vectorstore = rebuild_store()
    print(f"重建完成，共 {vectorstore.index.ntotal} 块")

    # 模拟"重启后从磁盘读回"——验证落盘的数据真的能检索
    vectorstore = load_store()
    results = vectorstore.similarity_search("怎么给函数加额外功能？", k=2)
    for result in results:
        print(result.page_content)
        print("="*50)
