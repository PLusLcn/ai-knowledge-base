# Day 6：Step 3 前端②——聊天界面打通到后端（计划 Day 12 / 3.2~3.4）

## 用时

- 2026-09-11：一次学习做完 3.2、3.3 和 3.4 的前端持久化部分。
- ⚠️ 事后复盘：这一次的量等于计划里 Day 12 的四条任务大半，**密度过高**。学生反馈"内容分配不合理，今天的太多了"、"前端的知识对我太陌生了，上一步还是没懂"。已调整教学节奏（见 `[[teaching-role]]`）并砍掉可选项。

## 本日做了什么

把 `ChatView.vue` 从"假数据摆 UI"做成"能真的问后端并显示答案"。

| 任务 | 内容 | 状态 |
|------|------|------|
| 3.2 | 消息左右分栏 + 时间显示 | ✅ 完成 |
| 3.3 | 输入框 + 发送按钮 + 调 `POST /api/v1/chat` + loading | ✅ 完成 |
| 3.4 | 历史对话记录（localStorage 持久化） | ⚠️ 代码写完，**决定回退砍掉** |

**验证结果**：输入问题回车 → 按钮转圈、输入框变灰 → 几秒后 AI 气泡里出现**后端 RAG 生成的真答案**。前后端全链路打通（这是本阶段最关键的一步）。

## 涉及的文件

| 文件 | 作用 |
|------|------|
| `frontend/src/api/chat.js` | **新建**。axios 实例 + `sendQuestion()`，网络细节从组件里抽出来 |
| `frontend/src/views/ChatView.vue` | 聊天页：消息列表 + 输入区 + 调用后端 |

## 核心代码段

### 1. axios 封装（`src/api/chat.js`）

```js
import axios from 'axios'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 60000, // RAG 要调 LLM，链路慢
})

export async function sendQuestion(question) {
  const res = await request.post('/chat', { question })
  return res.data.answer
}
```

### 2. 发送消息 + loading + 错误兜底（ChatView.vue）

```js
async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return // 空内容 / 请求中，都不发

  messages.value.push({ id: nextId++, role: 'user', content: text, time: now() })
  input.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const answer = await sendQuestion(text)
    messages.value.push({ id: nextId++, role: 'ai', content: answer, time: now() })
  } catch (e) {
    messages.value.push({ id: nextId++, role: 'ai', content: `请求失败：${e.message}`, time: now() })
  } finally {
    loading.value = false // 无论成功失败都要恢复，否则按钮永远转圈
    scrollToBottom()
  }
}
```

### 3. 滚到底部

```js
const listRef = ref(null) // 模板里 <div ref="listRef" class="message-list">

function scrollToBottom() {
  nextTick(() => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
```

## 本日知识点

### ⭐ 一、axios 封装的三件套

| 配置 | 值 | 为什么 |
|------|-----|-------|
| `baseURL` | `/api/v1` | **必须是相对路径**。写死 `http://127.0.0.1:8000` 会触发浏览器跨域（CORS）被拦；相对路径走 Vite 代理转发 |
| `timeout` | `60000` | axios 默认**不超时**（无限等）。RAG 链路 3~20 秒正常，后端卡死时要有反馈 |
| 返回值 | `res.data.answer` | axios 的 `res` 是 `{ data, status, headers }` 的壳，后端响应体在 `res.data` |

### ⭐ 二、loading 一个变量管三处

```
loading = true  →  ① el-button 转圈并禁用
                   ② el-input 变灰不可输入
                   ③ send() 开头的 if 挡住重复发送
```

### ⭐ 三、try / catch / finally

- `try`：可能出错的代码（网络请求一定会失败过几次）
- `catch (e)`：接住错误，`e.message` 显示在气泡里，而不是白屏
- `finally`：**成功失败都执行**。`loading = false` 必须放这里，否则失败后按钮永远转圈

### ⭐ 四、模板 ref + nextTick

- `ref="listRef"` + `const listRef = ref(null)` → 拿到**真实 DOM 元素**（Vue 里操作 DOM 的唯一常规入口）
- `nextTick(cb)`：数据变了但 DOM 还没渲染完，此刻读 `scrollHeight` 是**旧值**。必须等 Vue 渲染完再滚

### ⭐ 五、CSS 布局的两个独立轴

- `.message { display: flex; justify-content: flex-end/flex-start }` → 控制**左右**（谁靠哪边）
- 气泡 + 时间要**上下**排列 → 必须再套一层 `.bubble-wrap { flex-direction: column }`
- 一个元素没法同时横又纵，**方向冲突就套一层容器**
- `max-width: 70%` 放在 `.bubble-wrap` 上（不是 `.bubble`），否则时间那行不受约束会和气泡错位

### 六、localStorage（已决定砍掉，仅备查）

- 只能存**字符串** → 进出要 `JSON.stringify` / `JSON.parse`
- 特性：按域名隔离、永久有效（除非清缓存）、约 5MB、**服务器读不到**
- Vue 里 `watch` 一个数组要加 `{ deep: true }`：`.value` 始终是同一个数组对象，`push` 不换对象，浅监听认为"没变化"
- 恢复历史后 `nextId` 必须重算（取最大 id + 1），否则 id 撞车 → `:key` 重复 → Vue 复用 DOM 认错消息

## 面试常见问题

1. 前端怎么和后端联调的？为什么 `baseURL` 写 `/api/v1` 而不是完整地址？（**代理 + 跨域**）
2. 请求过程中怎么防止用户重复点击发送？（**loading 状态三处联动**）
3. 请求失败怎么处理？（**try/catch/finally + 错误提示上屏，不让页面白屏**）
4. `nextTick` 是干什么的？（**等 DOM 更新完再操作**）

## 犯的错

| 问题 | 原因 | 解决 |
|------|------|------|
| `sendQuestion is not defined` | 用了函数但忘了 `import` | 补 `import { sendQuestion } from '../api/chat'` |
| `watch is not defined` | 同上，`import { ref, nextTick }` 漏了 `watch` | 补上 |
| 时间和气泡左右并排 | 模板少了一层 `.bubble-wrap`，而 `.message` 是横向 flex | 把 `.bubble` 和 `.time` 包进 `.bubble-wrap` |

> **规律**：三次报错里两次是"用了但没 import"。改完代码先扫一眼顶部的 import 列表。

## 下一步

### 路线已调整（2026-09-11）：砍掉可选项，优先能投简历

| 保留 | 砍掉 |
|------|------|
| 前端能聊天、能通后端 ✅（已完成） | ❌ 多轮对话（改后端 prompt 带历史） |
| 一个最简单的上传按钮 | ❌ 聊天记录 localStorage 持久化 |
| README + 项目截图 | ❌ 打字机效果、文档列表美化、RAGAS |

**理由**：项目二是简历项目，六条简历描述里五条是 RAG，前端只占一条。前端**不需要精通**，只需要能讲清"页面怎么和后端说话"。

### 接下来两次学习

1. **下次（不写代码）**：把前端链路串一遍 —— `index.html` → `main.js` → `App.vue` → `router/index.js` → `ChatView.vue`，搞清楚"浏览器输入网址后到底发生了什么"。目标是让前端不再是黑盒。
2. **再下次**：Day 13 文件上传（3.5~3.7），前端用 Element Plus 的 `el-upload`，后端新写"接收文件 → 存盘 → 加载 → 切分 → 重建 FAISS"接口。
