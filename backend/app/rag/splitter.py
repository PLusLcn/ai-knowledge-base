from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_docs(docs, chunk_size=200, chunk_overlap=20):
    # 1. 创建 RecursiveCharacterTextSplitter
    # 2. split_documents(docs) 接收 Document 列表，返回切好的小 Document 列表
    # 3. 返回结果
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    return chunks
