from langchain_core.prompts import ChatPromptTemplate

RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """你是一个知识库问答助手。
        请严格基于下面的参考资料回答问题，如果资料里没有答案，就明确说不知道。

        参考资料：
        {context}""",
    ),
    ("user", "{question}"),
])

HYDE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """你是一个检索辅助器。用户会给你一个问题，你不需要回答这个问题本身，
        而是虚构一段"可能存在于某份技术文档/教程中的正文段落"，这段话写出来是为了
        帮向量检索找到相关资料。

        要求：
        1. 写成书面、陈述句的教程正文，不要对话腔，不要"我来解释""你可以这样做"这类口吻；
        2. 段落里包含和该主题强相关的关键词；
        3. 只输出正文本身，不要任何开场白、解释或结尾。""",
    ),
    ("user", "问题：{question}\n\n请写出对应的假设文档段落："),
])

if __name__ == "__main__":
    msgs = RAG_PROMPT.format_messages(
        context="Python 装饰器是用 @ 符号标记、能给函数添加额外功能的写法。",
        question="什么是装饰器？",
    )
    for m in msgs:
        print(f"[{m.type}]\n{m.content}\n")
