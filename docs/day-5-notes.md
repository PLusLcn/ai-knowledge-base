# Day 5：Step 3 前端①——Vue3 工程骨架与 SPA 认知（计划 Day 12 / 3.1）

## 用时

- 2026-09-09：选定先做前端（RAGAS 压后），搭起 Vue3 工程骨架并验证前后端连通（3.1 完成）。

## 本日做了什么

项目二此前只有 backend，本日新建 Vue3 前端工程。技术栈**照搬项目一**（Vue 3.5 + Vite 8 + Element Plus + vue-router + axios），只改一处差异：dev 代理的后端端口（项目一 8001 → 项目二 8000）。

本日只搭骨架，不写业务代码。两个验证都通过：
1. `npm run dev` 打开页面能正常显示
2. 浏览器访问 `http://localhost:5173/api/v1/health` 返回 `{"status":"ok"}`（代理通、前后端已连上）

## 目录结构（新建的 frontend/）

```
frontend/
├── index.html          # SPA 唯一 HTML 壳
├── vite.config.js      # Vite 配置：plugin-vue + /api 代理
├── package.json        # 依赖清单 + 命令
└── src/
    ├── main.js         # JS 入口：创建应用、装插件、mount
    ├── App.vue         # 根组件（放 <router-view/>）
    ├── router/
    │   └── index.js    # 路由表：URL → 组件
    └── views/
        └── ChatView.vue  # 聊天页（占位）
```

## ⭐ 重点一：文件职责链（SPA 的骨架）

| 文件 | 作用 | 一句话记 |
|------|------|---------|
| `index.html` | SPA 唯一的 HTML 页面，只有一个 `<div id="app">` 空壳，引入 `main.js` | 空房子，只有地基 |
| `src/main.js` | 创建 Vue 应用 → 装全局插件（Element Plus、router）→ `mount('#app')` | 装修工 |
| `src/App.vue` | 根组件，组件树顶端，放 `<router-view/>` 作为路由出口 | 房子主框架 |
| `src/router/index.js` | 路由表：URL 路径 → 显示哪个组件 | 门牌号对照表 |
| `src/views/ChatView.vue` | 页面级组件，一个 URL 对应一个 | 具体房间 |
| `vite.config.js` | `plugin-vue` 让 `.vue` 能被编译；`server.proxy` 把 `/api` 转给后端 | 施工设备清单 |
| `package.json` | 依赖清单 + 命令（`dev`/`build`） | 材料单 |

## ⭐ 重点二：`npm run dev` 之后发生了什么（启动链路）

1. Vite 启动**开发服务器**（5173 端口）
2. 浏览器访问 `/` → Vite 返回 `index.html`
3. `index.html` 里的 `<script type="module" src="/src/main.js">` 让浏览器去请求 `main.js`
4. **Vite 实时编译**：浏览器看不懂 `.vue` 文件，`@vitejs/plugin-vue` 把它当场编译成普通 JS 再返回
5. `main.js` 执行 `createApp(App).use(...).mount('#app')` → Vue 把 `App.vue` 渲染进 `#app`
6. `App.vue` 里的 `<router-view/>` → router 看当前 URL 是 `/`，查出对应 `ChatView` 并渲染

**这就是 SPA（单页应用）**：整个站只有一个 html 文件，切页面不重新请求页面，只是 router 换个组件渲染（项目一的登录页/学生页就是这么切的）。

## ⭐ 重点三：`.vue` 文件的三段结构

```vue
<template>       <!-- 结构：HTML，写页面长什么样 -->
<script setup>   <!-- 逻辑：JS，ref / 函数 / 发请求 -->
<style scoped>   <!-- 样式：CSS -->
```

**`scoped` 是重点**：不加它样式会污染全局（改一个组件的样式，别的页面跟着变）。

## 执行的关键命令/地址

| 命令 / 地址 | 解释 |
|-----------|------|
| `npm install` | 在 `frontend/` 下装依赖（首次报错疑为网络超时，复跑成功，装 85 个包） |
| `npm run dev` | 启动前端 dev server → `http://localhost:5173/` |
| `..\venv\Scripts\python.exe -m uvicorn app.main:app --reload` | 在 `backend/` 下启动后端（默认端口 **8000**） |
| `http://localhost:5173/api/v1/health` | 走 Vite 代理打到后端，验证前后端连通 |

## 后端基线（前端要对接的接口）

- 前缀 `/api/v1`（`app/config.py` 的 `API_V1_PREFIX`）
- 现有唯一业务接口：`POST /api/v1/chat`，请求 `{"question": "..."}`，响应 `{"answer": "..."}`，**无状态**（不带历史）
- 暂无文件上传接口（Step 3 后半要补）

## 犯的错 & 需要注意的点

| 问题 | 原因 | 解决 |
|------|------|------|
| `npm install` 首次报错 | 疑为国内直连 npm 官方源网络超时（非 package.json 问题，复跑即成功） | 复跑；若持续失败可设镜像 `npm config set registry https://registry.npmmirror.com` |
| 代理端口照抄项目一 | 项目一后端是 **8001**，项目二是 **8000**；照抄不改 → 所有 `/api` 请求 404 | `vite.config.js` 里 `proxy['/api'].target` 必须是 `http://127.0.0.1:8000` |

## 下一步

- **第 2 小步**：`ChatView.vue` 做成聊天界面——消息列表（用户靠右、AI 靠左）+ 输入框 + 发送按钮，**先用假数据摆 UI**
- 第 3 小步：`api/chat.js` 封装 axios 接 `POST /chat`，加 loading
- 第 4 小步：历史对话 / 多轮
