import axios from 'axios'

// 创建一个 axios 实例：统一 baseURL + 超时
const request = axios.create({
    baseURL: '/api/v1',
    timeout: 60000, // RAG 要调 LLM，链路慢，给 60 秒
})

// 问问题：POST /chat，请求体 { question }，返回答案字符串
export async function sendQuestion(question) {
    const res = await request.post('/chat', { question })
    return res.data.answer
}
