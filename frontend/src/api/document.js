import axios from 'axios'

// 上传单独一个 axios 实例：重建知识库要重跑嵌入模型，比问答更慢
const request = axios.create({
    baseURL: '/api/v1',
    timeout: 180000, // 3 分钟
})

// 上传文档：POST /documents/upload
// 成功返回后端的响应体 { filename, size, chunks, message }
export async function uploadDocument(file) {
    const formData = new FormData()
    formData.append('file', file)
    const res = await request.post('/documents/upload', formData)
    return res.data
}
// 拉取知识库里的文件名列表：GET /documents
export async function listDocuments() {
    const res = await request.get('/documents')
    return res.data.files
}

