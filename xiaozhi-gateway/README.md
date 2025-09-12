# 小智AI WebSocket网关

一个轻量级的Node.js网关，用于连接前端应用和小智AI语音服务。提供PCM音频到Opus转码、实时文本传输、TTS音频服务等功能。

## 🚀 特性

- ✅ **会话管理**: 支持多用户并发会话
- ✅ **音频转码**: PCM 16kHz单声道转Opus格式
- ✅ **实时通信**: WebSocket双向通信
- ✅ **TTS服务**: 音频文件存储和URL服务
- ✅ **打断功能**: 支持用户打断当前对话
- ✅ **健康检查**: 完整的服务监控
- ✅ **日志记录**: 详细的操作日志
- ✅ **Docker化**: 开箱即用的容器部署

## 📋 系统要求

- Node.js >= 18.0.0
- 小智AI服务端访问权限
- (可选) Docker用于容器化部署

## 📦 安装

### 1. 克隆和安装依赖

```bash
git clone <your-repo-url>
cd xiaozhi-gateway
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置小智AI服务信息：

```env
# 小智AI WebSocket服务配置
XIAOZHI_SERVER_URL=wss://api.tenclass.net/xiaozhi/v1/

# 小智AI OAuth认证配置
XIAOZHI_AUTH_URL=https://xiaozhi.me
XIAOZHI_CLIENT_ID=your_client_id_here
XIAOZHI_CLIENT_SECRET=your_client_secret_here
XIAOZHI_REDIRECT_URI=http://localhost:3000/auth/callback

# 服务器配置
PORT=3000
NODE_ENV=production

# TTS配置 (memory或file)
TTS_STORAGE=memory
TTS_MAX_AGE=300000
```

**重要**：你需要先在小智AI开发者后台申请 `CLIENT_ID` 和 `CLIENT_SECRET`。

### 3. 首次授权登录

**首次启动服务前，需要完成OAuth授权：**

```bash
# 启动服务
npm run dev
```

然后在浏览器中访问：**http://localhost:3000/auth/login**

这会重定向到小智AI授权页面，登录后自动跳转回来并保存访问令牌。

### 4. 正常启动服务

```bash
# 开发模式
npm run dev

# 生产模式
npm run build
npm start
```

## 🐳 Docker部署

### 构建镜像

```bash
docker build -t xiaozhi-gateway .
```

### 运行容器

```bash
docker run -d \
  --name xiaozhi-gateway \
  -p 3000:3000 \
  -e XIAOZHI_WS_URL=wss://your-xiaozhi-server.com/ws \
  -e XIAOZHI_TOKEN=your_token_here \
  -v $(pwd)/logs:/app/logs \
  xiaozhi-gateway
```

### 使用docker-compose

```yaml
version: '3.8'
services:
  gateway:
    build: .
    ports:
      - "3000:3000"
    environment:
      - XIAOZHI_WS_URL=wss://your-xiaozhi-server.com/ws
      - XIAOZHI_TOKEN=your_token_here
      - TTS_STORAGE=memory
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
```

## 📡 API文档

### 0. 授权相关

**GET** `/auth/login` - 重定向到小智AI授权页面

**GET** `/auth/callback` - OAuth回调处理（自动处理）

**GET** `/auth/status` - 查询授权状态

```json
{
  "authorized": true,
  "tokenInfo": {
    "expiresAt": "2024-01-01T12:00:00.000Z",
    "tokenType": "Bearer",
    "scope": "openid profile voice"
  },
  "loginUrl": null
}
```

### 1. 创建会话

**POST** `/session`

```json
{
  "userId": "user123"
}
```

**Success Response:**
```json
{
  "sessionId": "uuid-session-id",
  "wsUrl": "ws://localhost:3000/ws/uuid-session-id"
}
```

**Unauthorized Response (401):**
```json
{
  "error": "UNAUTHORIZED",
  "message": "需要授权才能创建会话",
  "loginUrl": "/auth/login"
}
```

如果收到401错误，前端应该引导用户访问 `loginUrl` 完成授权。

### 2. WebSocket连接

连接到返回的 `wsUrl`：

```javascript
const ws = new WebSocket('ws://localhost:3000/ws/your-session-id');

// 发送PCM音频数据 (Buffer)
ws.send(pcmAudioBuffer);

// 发送控制消息
ws.send(JSON.stringify({
  type: 'interrupt'  // 打断当前对话
}));

// 接收消息
ws.on('message', (data) => {
  const message = JSON.parse(data);
  
  switch(message.type) {
    case 'stt':      // 语音识别结果
    case 'llm':      // AI响应文本  
    case 'tts_start': // TTS开始
    case 'tts_url':   // TTS音频URL
    case 'tts_end':   // TTS结束
    case 'error':     // 错误信息
  }
});
```

### 3. TTS音频服务

**GET** `/tts/{tts-id}`

返回音频文件（Opus格式）。

### 4. 健康检查

**GET** `/healthz`

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "services": {
    "xiaozhi": "connected",
    "sessions": {
      "active": 5,
      "total": 10
    },
    "tts": {
      "stored": 25,
      "memoryUsage": "12.5MB"
    }
  },
  "uptime": 3600000,
  "version": "1.0.0"
}
```

## 🔧 前端集成示例

```javascript
class XiaozhiClient {
  constructor() {
    this.sessionId = null;
    this.ws = null;
  }

  // 1. 创建会话
  async createSession(userId) {
    const response = await fetch('/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId })
    });
    
    const { sessionId, wsUrl } = await response.json();
    this.sessionId = sessionId;
    
    // 2. 连接WebSocket
    this.ws = new WebSocket(wsUrl);
    this.setupEventListeners();
  }

  // 3. 发送音频
  sendAudio(pcmBuffer) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(pcmBuffer);
    }
  }

  // 4. 打断对话
  interrupt() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interrupt' }));
    }
  }

  setupEventListeners() {
    this.ws.on('message', (data) => {
      const message = JSON.parse(data);
      
      switch(message.type) {
        case 'stt':
          console.log('识别结果:', message.data.text);
          break;
          
        case 'llm':
          console.log('AI回复:', message.data.text);
          break;
          
        case 'tts_url':
          // 播放TTS音频
          const audio = new Audio(message.data.url);
          audio.play();
          break;
      }
    });
  }
}

// 使用示例
const client = new XiaozhiClient();
await client.createSession('user123');
```

## 🎛️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `XIAOZHI_WS_URL` | 小智AI WebSocket地址 | 必填 |
| `XIAOZHI_TOKEN` | 小智AI认证令牌 | 必填 |
| `PORT` | 服务端口 | `3000` |
| `TTS_STORAGE` | TTS存储方式 | `memory` |
| `TTS_MAX_AGE` | TTS文件过期时间(ms) | `300000` |
| `LOG_LEVEL` | 日志级别 | `info` |
| `SESSION_TIMEOUT` | 会话超时时间(ms) | `600000` |
| `MAX_SESSIONS` | 最大会话数 | `1000` |

### 音频参数

- **格式**: PCM 16-bit
- **采样率**: 16kHz
- **声道**: 单声道 (Mono)
- **编码**: Opus (网关自动转换)

## 🔍 故障排查

### 1. 连接失败

```bash
# 检查小智服务可达性
curl -I https://your-xiaozhi-server.com

# 检查WebSocket连接
wscat -c ws://localhost:3000/ws/test-session-id
```

### 2. 音频问题

- 确保PCM格式正确：16kHz, 16-bit, 单声道
- 检查音频数据大小：每帧应为 960 * 2 = 1920 字节

### 3. 查看日志

```bash
# 实时日志
tail -f logs/combined.log

# 错误日志
tail -f logs/error.log
```

### 4. 健康检查

```bash
curl http://localhost:3000/healthz
```

## 🛠️ 开发指南

### 项目结构

```
src/
├── index.ts          # 主入口服务器
├── types.ts          # TypeScript类型定义
├── sessionManager.ts # 会话管理
├── audioConverter.ts # 音频转码
├── ttsManager.ts     # TTS文件管理
├── xiaozhiClient.ts  # 小智AI客户端
└── logger.ts         # 日志工具
```

### 开发命令

```bash
npm run dev          # 开发模式
npm run build        # 构建
npm run lint         # 代码检查
npm test             # 运行测试
```

## 📄 协议说明

### 小智AI WebSocket协议

参考小智ESP32项目的协议文档：
- [WebSocket协议](https://github.com/78/xiaozhi-esp32/blob/main/docs/websocket.md)
- [MQTT+UDP协议](https://github.com/78/xiaozhi-esp32/blob/main/docs/mqtt-udp.md)

### 音频帧格式

网关使用小智协议v3格式：

```
[版本(1byte)][会话ID长度(1byte)][会话ID][帧ID(4bytes)][是否最后帧(1byte)][音频数据长度(4bytes)][音频数据]
```

## 🤝 贡献

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📝 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 🙋 支持

- 提交 [Issue](../../issues) 报告bug
- 查看 [Wiki](../../wiki) 获取更多文档
- 加入交流群讨论

---

**注意**: 确保遵循小智AI的使用条款和API限制。