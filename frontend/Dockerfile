# ============================================================
# 前端镜像（多阶段：Node 编译 → nginx 只发文件）
# 构建上下文 = 项目根目录，不是 frontend/
#   docker build -f frontend/Dockerfile -t kb-frontend .
#                                              ↑ 这个点 = 项目根
# ============================================================

# ------------------------------------------------------------
# 阶段 1：盖房子（需要 Node）
#   这一步只是"施工队"，它的产物是 /build/dist 这一个目录
#   阶段结束后整个 node 镜像被丢弃，不会出现在最终镜像里
# ------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /build

# ❶ 先只拷依赖清单 → 单独装依赖
#    和 backend/Dockerfile 完全同一个套路（叠盘子：不常变的放底下）
#    以后你改 Vue 代码，这一层照样走缓存，不用重装 node_modules
COPY frontend/package.json frontend/package-lock.json ./

#    npm ci = 严格按 package-lock.json 装，版本可复现
#    （npm install 会"顺便"升级版本，构建镜像时不要用）
#    --registry 换成国内镜像源，否则这一步能卡很久
RUN npm ci --registry=https://registry.npmmirror.com

# ❷ 再拷源码 → 编译
#    注意：node_modules/ 在 .dockerignore 里被排除了，
#    所以这里拷进来的是"干净的源码"，不会用本机的 node_modules 覆盖容器里的
COPY frontend/ ./

RUN npm run build          # 产出 /build/dist


# ------------------------------------------------------------
# 阶段 2：只留房子（不需要 Node）
#   从这里开始是一个全新的镜像，阶段 1 的 node、npm、源码、node_modules 全都不在
#   最终镜像 ≈ nginx 本体(50MB) + 你的 dist(几百 KB)
# ------------------------------------------------------------
FROM nginx:alpine

# ⭐ COPY --from=build —— 跨阶段搬文件，只搬这一个目录
#    这就是多阶段构建的全部魔法：施工队的东西一件不带，只带房子
COPY --from=build /build/dist /usr/share/nginx/html

# 换掉 nginx 自带的默认配置（默认配置只会发一个欢迎页，没有 /api 转发）
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx 官方镜像自带 CMD ["nginx", "-g", "daemon off;"]，不用写
# （对照 backend：那边是 python 镜像，要自己写 CMD 启动 uvicorn）
