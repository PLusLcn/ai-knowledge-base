import requests                 # 发 HTTP 请求（和之前 requests 调 LLM 用的是同一个库）
from langchain_core.embeddings import Embeddings  # ← 新东西：LangChain 的嵌入抽象基类
from app.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBEDDING_MODEL

class SiliconFlowEmbeddings(Embeddings):
    # 继承 Embeddings 基类 = 向 LangChain 声明"我也是个嵌入工具，可以配合 FAISS/Retriever 用"
    # 对比之前：ChatOpenAI 是官方写好的类；这里我们自己写一个，LangChain 一视同仁
    def __init__(self, api_key: str, base_url: str, model: str):
        # 构造函数：把配置存到 self 上，之后每个方法都能用 self.xxx 取
        # 对比 test_llm.py：之前配置是脚本里的局部变量，写一次用完；改成类后可以反复实例化复用
        self.api_key = api_key      # self.xxx = 这个对象自己的属性
        self.base_url = base_url
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # LangChain 规定的方法①：嵌入"多个"文档 → 返回"多个"向量
        # 对比调 LLM：调 LLM 一次只能聊一段消息；这里一次请求能把整个列表发给服务器，服务器返回对应个数的向量
        resp = requests.post(
            f"{self.base_url}/embeddings",        # URL：和调 LLM 的 /chat/completions 不同 → 这里是 /embeddings（同一个服务器的两个"端点"）
            headers={
                "Authorization": f"Bearer {self.api_key}",  # 认证头，和 test_llm.py 一模一样
                "Content-Type": "application/json",         # 声明发送的是 JSON
            },
            json={"model": self.model, "input": texts},     # 请求体：model=嵌入模型名，input=要嵌入的文本列表
        )
        resp.raise_for_status()   # 非 200 直接抛异常（llm.py 里学过的 raise_for_status，这里也适用）
        data = resp.json()["data"]  # 解析响应 JSON，data 是一个列表，每项对应一段输入文本的结果
        # 关键：data 的顺序 = 传入 input 的顺序，第 i 项就是第 i 段文本的向量
        return [item["embedding"] for item in data]  # 列表推导式：把每项的 embedding 字段抽出来，拼成向量列表

    def embed_query(self, text: str) -> list[float]:
        # LangChain 规定的方法②：嵌入"单个"问题 → 返回"单个"向量
        # 原理：把 1 个问题包成 [text] 列表 → 调 embed_documents → 返回的列表取第 0 个
        return self.embed_documents([text])[0]

def get_embedding():
    # 把类的三个构造参数全部换成从 config 读的常量
    return SiliconFlowEmbeddings(SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBEDDING_MODEL)

if __name__ == "__main__":
    # 测试代码
    embedder = get_embedding()
    vec = embedder.embed_query("Python 装饰器是什么")  # 单个问题 → 单个向量
    print("维度:", len(vec))        # 应该是 1024
    print("前5个数字:", vec[:5])    # 向量是浮点数列表