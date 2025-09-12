# Xiaozhi AI WebSocket Gateway Dockerfile
FROM node:18-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache python3 make g++ ffmpeg-dev

# 设置工作目录
WORKDIR /app

# 复制package文件并安装依赖
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# 复制源代码
COPY . .

# 构建TypeScript
RUN npm run build

# 生产阶段
FROM node:18-alpine AS production

# 安装运行时依赖
RUN apk add --no-cache ffmpeg

# 创建非root用户
RUN addgroup -g 1001 -S gateway && \
    adduser -S gateway -u 1001

# 设置工作目录
WORKDIR /app

# 从builder阶段复制文件
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

# 创建日志和存储目录
RUN mkdir -p logs tts-storage && \
    chown -R gateway:gateway /app

# 切换到非root用户
USER gateway

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/healthz', (res) => { \
    process.exit(res.statusCode === 200 ? 0 : 1) \
  }).on('error', () => process.exit(1))"

# 启动应用
CMD ["node", "dist/index.js"]