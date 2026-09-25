<template>
  <div class="chat-view">
    <!-- 消息列表区 -->
    <div ref="listRef" class="message-list">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message"
        :class="msg.role"
      >
        <div class="bubble-wrap">
          <!-- 用户提问：纯文本插值。{{ }} 会自动转义，天然安全 -->
          <div v-if="msg.role === 'user'" class="bubble">{{ msg.content }}</div>
          <!-- AI 回答：markdown 渲染。必须配 DOMPurify，见下方 renderMarkdown -->
          <div v-else class="bubble" v-html="renderMarkdown(msg.content)"></div>
          <div class="time">{{ msg.time }}</div>
        </div>
      </div>
    </div>

    <!-- 已上传文档列表 -->
    <div v-if="documents.length" class="doc-list">
      <div v-for="doc in documents" :key="doc" class="doc-item">
        {{ doc }}
      </div>
    </div>

    <!-- 底部输入区 -->
    <div class="input-bar">
      <el-upload
        action="#"
        accept=".txt"
        :show-file-list="false"
        :http-request="customUpload"
      >
        <el-button :loading="uploading">上传文档</el-button>
      </el-upload>
      <el-input
        v-model="input"
        placeholder="输入问题…"
        :disabled="loading"
        @keyup.enter="send"
      />
      <el-button type="primary" :loading="loading" @click="send">发送</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { sendQuestion } from '../api/chat'
import { ElMessage } from 'element-plus'
import { uploadDocument, listDocuments } from '../api/document'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 把 AI 回答从 markdown 转成 HTML，交给 v-html 显示
//
// ⚠️ 为什么要 DOMPurify 过一遍？
//    模型输出的内容会变成页面上【真的 HTML】。而 v-html 的内容会被浏览器当代码执行，
//    一段 <img src=x onerror="..."> 就能跑脚本。
//    虽然这里是本地单机应用、文档也是自己传的，风险不高，
//    但"把模型输出直接塞进 v-html"是不该养成的习惯 —— 将来接公开文档就危险了。
//    DOMPurify 会把危险标签和属性洗掉，只留安全的展示类标签。
//
// ⚠️ 注意这里【只对 AI 回答】做渲染。用户提问走 {{ }} 纯文本插值，
//    Vue 会自动转义。两条路分开走，是刻意的。
function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text ?? ''))
}

// 生成 "HH:MM" 格式的当前时间
function now() {
  const d = new Date()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

function defaultMessages() {
  return [
    { id: 1, role: 'user', content: '什么是 Python 装饰器？', time: now() },
    { id: 2, role: 'ai', content: '装饰器是一个接收函数并返回新函数的高阶函数……', time: now() },
  ]
}

let nextId = 3
const messages = ref(defaultMessages())
const documents = ref([])//后端知识库里的文件名列表
const input = ref('')
const loading = ref(false) // 是否正在等后端回答
const listRef = ref(null) // 指向消息列表这个 DOM 元素
const uploading = ref(false) // 是否正在上传

// el-upload 自定义上传：它把选中的文件交给我们，我们走自己的 axios
async function customUpload(options) {
  uploading.value = true
    try {
    const data = await uploadDocument(options.file)
    ElMessage.success(data.message)
    await loadDocuments()
  } catch (e) {
    ElMessage.error(`上传失败：${e.message}`)
  } finally {
    uploading.value = false
  }
}

// 从后端拉取知识库文件列表
async function loadDocuments() {
  try {
    documents.value = await listDocuments()
  } catch (e) {
    ElMessage.error(`加载文档列表失败：${e.message}`)
  }
}

onMounted(loadDocuments)

// 滚到消息列表最底部
function scrollToBottom() {
  nextTick(() => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return // 空内容或正在请求中，都不发

  messages.value.push({ id: nextId++, role: 'user', content: text, time: now() })
  input.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const answer = await sendQuestion(text)
    messages.value.push({ id: nextId++, role: 'ai', content: answer, time: now() })
  } catch (e) {
    messages.value.push({
      id: nextId++,
      role: 'ai',
      content: `请求失败：${e.message}`,
      time: now(),
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  border: 1px solid #eee;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message {
  display: flex;
  margin-bottom: 12px;
}

.message.user {
  justify-content: flex-end;
}

.message.ai {
  justify-content: flex-start;
}

.bubble-wrap {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}

.message.user .bubble-wrap {
  align-items: flex-end;
}

.message.ai .bubble-wrap {
  align-items: flex-start;
}

.bubble {
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.5;
  word-break: break-word;
}

.message.user .bubble {
  background: #3b9bfa;
  color: #fff;
}

.message.ai .bubble {
  background: #f4f4f5;
  color: #303133;
}

/* ---------- AI 回答里 markdown 的样式 ----------
   ⚠️ 为什么是 :deep() 而不是直接写 p / pre / code？
   <style scoped> 的原理是给元素加一个唯一属性（如 data-v-xxx），
   但 v-html 注入的 HTML 是【运行时才生成的】，拿不到这个属性，
   所以 scoped 的选择器一条都命中不了。
   :deep() 的作用就是告诉 Vue："这一段里面的选择器不要加那个属性，往下穿透"。
   —— 不写 :deep() 的话，代码块会是一坨没有任何背景和换行的白板文字。 */
.bubble :deep(p) {
  margin: 0 0 8px;
}
.bubble :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;      /* 长代码横向滚动，不撑破气泡 */
  margin: 8px 0;
}
.bubble :deep(pre code) {
  background: none;      /* 行内 code 有底色，代码块里的不要双层 */
  padding: 0;
  color: inherit;
}
.bubble :deep(code) {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 5px;
  border-radius: 3px;
}
.bubble :deep(ul),
.bubble :deep(ol) {
  padding-left: 20px;
  margin: 0 0 8px;
}
.bubble :deep(li) {
  margin: 2px 0;
}
.bubble :deep(h1),
.bubble :deep(h2),
.bubble :deep(h3) {
  font-size: 15px;
  margin: 10px 0 6px;
}
.bubble :deep(blockquote) {
  border-left: 3px solid #dcdfe6;
  padding-left: 10px;
  margin: 8px 0;
  color: #666;
}
.bubble :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
}
.bubble :deep(th),
.bubble :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
}

.time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid #eee;
}
.doc-list {
  max-height: 120px;
  overflow-y: auto;
  padding: 8px 12px;
  border-top: 1px solid #eee;
  font-size: 13px;
  color: #666;
}

.doc-item {
  line-height: 1.8;
}

</style>
