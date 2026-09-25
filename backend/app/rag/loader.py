from langchain_community.document_loaders import TextLoader
from pathlib import Path

def load_txt(path: str) -> list:
    # 1. 创建 TextLoader，指定 utf-8 编码
    # 2. 调用 load() 拿文档列表
    # 3. 返回结果
    loader = TextLoader(path, encoding="utf-8")
    docs = loader.load()
    return docs

def load_dir(dir_path: str) -> list:
    """加载目录下所有 .txt 文件，合并成一个文档列表"""
    docs = []
    for path in sorted(Path(dir_path).glob("*.txt")):
        docs.extend(load_txt(str(path)))
    return docs

if __name__ == "__main__":
    docs = load_txt("data/samples/python-basics.txt")
    print(len(docs))
    print(docs[0].metadata)
    print(docs[0].page_content[:80])
