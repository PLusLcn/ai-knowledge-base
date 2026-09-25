# Day 7：前端链路串讲——浏览器里到底发生了什么（不写代码日）

## 用时

- 2026-09-16：一次学习，**全程不写新代码**，只把已有代码的两条链路串一遍。收尾删掉 3.4 的 localStorage 残留。

> 这次的目标不是"多做功能"，是**让前端不再是黑盒**。项目二定位是简历项目，前端只占六条描述里的一条，要求降到"能跑 + 能讲清页面怎么和后端说话"。

## 本日做了什么

| 任务 | 内容 | 状态 |
|------|------|------|
| 链路串讲① | 页面渲染链路：`index.html` → `main.js` → `App.vue` → `router` → `ChatView.vue` | ✅ |
| 链路串讲② | 请求链路：`send()` → `api/chat.js` → vite 代理 → FastAPI → RAG → 回显 | ✅ |
| 3.4 收尾 | 删掉 localStorage 残留（4 处删除 + 2 处改写，自己动手） | ✅ |
| 实操 | 打开 F12 → Network，亲眼看到真实的 `chat` 请求 | ✅ |

**验证结果**：刷新页面回到两条默认消息（不再保留聊天记录）→ 证明 localStorage 已彻底移除。Network 面板里能看到 `chat` 请求的 URL、Payload、Response 三处内容。

## 涉及的文件

| 文件 | 作用 |
|------|------|
| `frontend/index.html` | 唯一的 HTML，几乎空壳，只有挂载点 + 一行 script |
| `frontend/src/main.js` | **入口**：创建应用、装插件、挂载 |
| `frontend/src/App.vue` | 根组件，只有一行 `<router-view />` |
| `frontend/src/router/index.js` | 路由表：URL 路径 → 哪个组件 |
| `frontend/src/views/ChatView.vue` | 真正的聊天页面 |
| `frontend/src/api/chat.js` | axios 实例 + `sendQuestion()` |
| `frontend/vite.config.js` | **代理配置**（本次重点） |

---

## 链路一：页面是怎么显示出来的

```
浏览器访问 localhost:5173/
  ↓ ① Vite 返回 index.html（空壳：一个空 div + 一行 script）
  ↓ ② 执行 <script src="/src/main.js">
main.js
  ↓ ③ createApp(App).use(ElementPlus).use(router).mount('#app')
  ↓    ← 这句是"焊接点"：把空 div 和 Vue 连起来
App.vue
  ↓ ④ 渲染出 <router-view />（占位符，本身不画内容）
router/index.js
  ↓ ⑤ 看 URL 是 "/" → 匹配到 routes 里的 ChatView
ChatView.vue
  ↓ ⑥ 渲染 template：消息列表 + 输入框
屏幕出现聊天界面 ✅
```

**一句话记住：HTML 是壳，main.js 是入口，App.vue 是容器，router 是调度，ChatView.vue 才是真正的页面。**

### 关键代码

```js
// main.js —— 链式调用一口气做四件事
const app = createApp(App)   // ① 用根组件创建应用实例
app.use(ElementPlus)          // ② 装插件：全局注册 el-* 组件 + 样式
app.use(router)               // ③ 装插件：接入路由能力
app.mount('#app')             // ④ 挂载到 index.html 里那个空 div
```

`.use()` 返回的仍是实例本身，所以能一直点下去（链式写法）。

```js
// router/index.js
const routes = [{ path: '/', name: 'chat', component: ChatView }]
export default createRouter({
  history: createWebHistory(),  // URL 干净、无 #，靠 History API 换页不刷新
  routes,
})
```

## 链路二：点"发送"之后发生了什么

```
你按回车
  → ChatView.vue 的 send()
  → api/chat.js  sendQuestion()
  → axios 发 POST /api/v1/chat      ← 相对路径，打到 5173 自己身上
  → Vite 代理命中 /api 前缀 → 转发到 127.0.0.1:8000
  → FastAPI  POST /api/v1/chat
  → RAG 链路：HyDE → 向量检索 → BGE 重排 → 拼 prompt → 调 LLM
  → 返回 {"answer": "..."}
  → 原路返回，axios 取出 res.data.answer
  → messages.push(...) → Vue 响应式自动重绘 → 气泡出现
```

### 关键代码

```js
// api/chat.js —— 注意 baseURL 是相对路径，不是完整 URL
const request = axios.create({
  baseURL: '/api/v1',   // ← 这是整个代理机制的前提
  timeout: 60000,       // RAG 要调 LLM，链路慢，给 60 秒
})
export async function sendQuestion(question) {
  const res = await request.post('/chat', { question })
  return res.data.answer      // axios 已自动把 JSON 转成 JS 对象
}
```

实际请求地址 = `baseURL` + 路径 = `/api/v1` + `/chat` = `/api/v1/chat`，
相对的是**当前页面所在的源**，也就是 `http://localhost:5173` —— **不是 8000**。

```js
// vite.config.js —— 代理：以 /api 开头的请求，转发到后端
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,   // 转发时把 Host 头改成目标地址
    },
  },
},
```

---

## 本日知识点

### ⭐ 一、挂载点（mount）

`index.html` 里只留一个空 div `<div id="app"></div>`，`.mount('#app')` 把它和 Vue 应用接上。

`.mount()` 内部就是 `document.querySelector('#app')`。**找不到会怎样：**

- 不崩，只有一条控制台警告 `Failed to mount app: mount target selector "#app" returned null.`
- 页面**白屏**

**记住这个症状**：改了 id 之后白屏 + 一条 mount 警告 = 挂载点对不上，不是业务逻辑错。

### ⭐ 二、为什么 App.vue 只有一行

因为它是**容器**，不负责画具体内容。`<router-view />` 是个占位符，意思是"当前 URL 匹配到哪个组件，就把那个组件渲染在这个位置"。

坏处对照：如果把内容全塞进 `App.vue` 并删掉 router，**也能跑，而且更简单**。但下次加"文档管理页"就没地方放了，只能往同一个文件里堆；而且 `App.vue` 该放的是所有页面共用的东西（导航栏、全局布局），页面级逻辑属于页面组件。

**路由的价值在扩展性。**

### ⭐ 三、代理（本次最重要的点）

**问题**：前端在 5173，后端在 8000，端口不同 → 浏览器同源策略会拦掉响应。

**同源判定**：协议 + 域名 + 端口，三者全一样才算同源。

| | 前端页面 | 后端接口 | 同源？ |
|---|---|---|---|
| 协议 | `http` | `http` | ✅ |
| 域名 | `localhost` | `127.0.0.1` | ❌ 两个不同的主机名 |
| 端口 | `5173` | `8000` | ❌ |

**两种解法**：

1. 后端加 CORS 中间件（FastAPI 的 `CORSMiddleware`），明文允许 5173 来调
2. **前端做代理**，让请求根本不跨域 ← 本项目用这种

**代理的工作过程**：

```
① 浏览器 → localhost:5173/api/v1/chat
     同源，浏览器不拦 ✅
② Vite 收到，路径以 /api 开头，命中代理规则
③ Vite 转发 → 127.0.0.1:8000/api/v1/chat
     服务器对服务器，不经过浏览器，同源策略管不着 ✅
④ FastAPI 处理完返回
⑤ Vite 把响应原样交还浏览器
```

**关键认知：代理不是"绕过"浏览器的安全规则，而是让浏览器压根不需要用到那条规则。** 浏览器全程只跟 5173 说话，不知道 8000 的存在。

**延伸记忆：开发环境用 Vite proxy，生产环境用 Nginx 反向代理，做的是同一件事。** 项目一 Docker 部署里那份 nginx 配置就是干这个。

### 四、跨域的常见误解

写了绝对地址（`http://127.0.0.1:8000/...`）之后：

- 请求**照样会发出去**（很多人以为发不出去）
- 但浏览器会把**响应丢掉**，控制台报 CORS 错
- 你在 JS 里 `catch` 到的是报错，不是数据

所以报错位置在"拿不到数据"，根因在"跨域被拦"。

### 五、SPA（单页应用）的本质

浏览器从 Vite 拿到的 HTML 里**没有任何界面内容的痕迹**，整个界面是 JS 运行时"画"出来的。

- 换页面时不重新发请求、不白屏刷新，只是把 `<router-view>` 里的组件换掉 —— 这是"单页"的含义
- `.vue` 文件浏览器不认识，是 Vite 在后台翻译成 JS（`vite.config.js` 里的 `@vitejs/plugin-vue`）

### 六、单文件组件（SFC）三块

| 块 | 作用 |
|---|---|
| `<template>` | 长什么样（HTML 结构） |
| `<script setup>` | 有什么数据和逻辑；此块声明的变量/函数，模板里可直接用 |
| `<style scoped>` | 样式；`scoped` = 只对当前组件生效，选择器名字不怕重名 |

---

## 面试常见问题

1. **SPA 的页面渲染过程和传统多页应用有什么区别？**
   传统：每次请求后端返回一份完整 HTML。SPA：首次只拿到空壳 HTML + 一个入口 script，后续界面全部由 JS 渲染，换页不刷新。

2. **前端 5173、后端 8000，跨域怎么解决？**
   两种：后端配 CORS 中间件；或前端反向代理。本项目用 Vite proxy，原理是让请求先发给同源的开发服务器，由服务器转发给后端——服务器之间通信不受浏览器同源策略限制。生产环境对应的是 Nginx 反向代理。

3. **`baseURL` 为什么写 `/api/v1` 而不写 `http://127.0.0.1:8000/api/v1`？**
   相对路径才能让请求打到同源的 5173 上、由代理转发；写绝对地址会变成跨域，响应被浏览器丢掉。

4. **`app.mount('#app')` 做了什么？挂载点不存在会怎样？**
   把 Vue 应用实例挂到指定 DOM 元素上并触发首次渲染。挂载点是 `querySelector` 查的，找不到会白屏 + 控制台一条警告，不会抛异常崩掉。

5. **`App.vue` 里为什么只放 `<router-view />`？**
   根组件当容器，页面切换交给路由。这样新增页面只需改路由表，不用动根组件，也不用改 `main.js`。

---

## 踩的坑

| 现象 | 原因 | 解法 |
|------|------|------|
| F12 打开 Network 面板，列表**空白** | Network 面板**只记录它打开之后**发生的请求，打开前已加载完的请求不会显示 | 保持面板打开，按 F5 刷新页面，就会刷出一堆请求 |

---

## 下一步

- **Day 13 文件上传**（计划 3.5~3.7）：前端 `el-upload`，后端新写"接收文件 → 存盘 → 加载 → 切分 → 重建 FAISS"接口。
- 这块是**整个项目最硬的一段**，预估要 3~4 次学习。开讲前先列分步计划。
- 路线已砍（2026-09-11）：多轮对话、聊天记录持久化、打字机效果、文档列表美化、RAGAS。
- **保留**：能聊天通后端 ✅ + 一个最简上传按钮 + README 与截图。
