# Zoev4 Web版本 🎭🎤

Zoev4是一个集成了Live2D、小智AI和Zoev3音频系统的完整Web版本，提供语音交互、Live2D动画和智能对话的完整体验。

## ✨ 特性

- 🎭 **完整Live2D界面**: 移植自Zoev2的Live2D系统，支持表情和动作控制
- 🎤 **语音交互**: 集成Zoev3音频系统，支持Web浏览器语音录音
- 🤖 **小智AI对话**: 通过Zoev3连接小智AI，支持智能对话
- 🌐 **Web界面**: 完全基于浏览器，无需额外软件
- 🔄 **实时同步**: Live2D动画与AI回复实时同步

## 🏗️ 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web浏览器     │    │   Zoev4服务器    │    │   Zoev3系统     │
│  (Live2D界面)   │◄──►│  (HTTP + API)    │◄──►│ (小智AI连接)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        ▲                        ▲                        ▲
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   音频录制      │    │   音频桥接服务   │    │   OPUS编码      │
│  (WebRTC API)   │◄──►│  (WebSocket)     │◄──►│ (音频处理)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 快速启动

### 一键启动（推荐）

```bash
cd /Users/good/Desktop/Zoe-AI/Zoev4
python start_zoev4_web.py
```

启动后访问：
- **Zoev4完整版**: http://127.0.0.1:3000/index.html (推荐 - 完整功能含语音)
- **Zoev2兼容版**: http://127.0.0.1:3000/index_zoev2_original.html (仅文字聊天)
- **音频测试**: http://127.0.0.1:3000/web_audio_test.html

### 手动启动

如果需要单独启动各个服务：

1. **启动Zoev3系统**
```bash
cd /Users/good/Desktop/Zoe-AI/Zoev3
python main.py --skip-activation
```

2. **启动音频桥接服务**
```bash
cd /Users/good/Desktop/Zoe-AI/Zoev4
python zoev3_audio_bridge.py
```

3. **启动Web服务器**
```bash
cd /Users/good/Desktop/Zoe-AI/Zoev4
python server.py 3000
```

## 🎮 使用方法

### 1. Live2D交互
- 界面右上角有控制面板
- 支持表情控制、动作控制
- 可以折叠/展开控制面板

### 2. 语音对话 (核心功能)
- 点击麦克风按钮开始录音
- 使用OPUS编码实现高质量音频传输
- 系统自动将语音发送给小智AI
- AI回复会触发相应的Live2D表情和动作
- 支持实时录音状态显示和音频质量监控

### 3. 文本对话
- 在聊天框中输入文本
- 点击发送与AI进行文本对话
- 支持实时情感分析和Live2D响应
- 53种情感类型自动映射到Live2D动作

### 4. 智能情感系统
- 自动分析AI回复中的情感信息
- 支持情感同义词和多语言映射
- 动态Live2D表情响应：开心、生气、惊讶、思考等
- 表情和动作的优先级管理

## 🔧 配置说明

### 服务端口
- **Web服务器**: 3000 (HTTP)
- **音频桥接**: 8004 (WebSocket)
- **Zoev3音频**: 8890 (HTTP)

### 音频配置
- **采样率**: 16kHz
- **声道**: 单声道
- **编码**: OPUS (60ms帧)
- **格式**: PCM -> OPUS转换

## 📁 文件结构

```
Zoev4/
├── index.html              # 主Live2D界面
├── server.py               # Web服务器 (改造版)
├── zoev3_audio_bridge.py   # 音频桥接服务
├── web_audio_test.html     # 音频测试页面
├── start_zoev4_web.py      # 一键启动脚本
├── emotion_mapping.py      # 情感映射模块
├── libs/                   # Live2D库文件
├── Mould/                  # Live2D模型文件
└── README.md              # 本文档
```

## 🔍 故障排除

### 常见问题

1. **Web服务器无法启动**
   - 检查端口3000是否被占用
   - 使用 `lsof -i :3000` 查看端口占用情况

2. **音频功能不工作**
   - 确保浏览器已授权麦克风权限
   - 检查Zoev3服务是否正常运行
   - 确认音频桥接服务在端口8004运行

3. **Live2D不显示**
   - 检查libs和Mould目录是否完整
   - 确保浏览器支持WebGL
   - 查看浏览器控制台错误信息

### 调试模式

启用详细日志：
```bash
# 在各个服务启动时添加调试参数
PYTHONDONTWRITEBYTECODE=1 python start_zoev4_web.py
```

### 服务状态检查

```bash
# 检查所有相关端口
lsof -i :3000,8004,8890

# 检查Zoev3连接状态
curl http://127.0.0.1:8890/status

# 检查音频桥接状态
curl http://127.0.0.1:8004/health
```

## 🎯 API接口

### Live2D控制
```bash
# 表情控制
curl -X POST http://127.0.0.1:3000/api/live2d \
  -H "Content-Type: application/json" \
  -d '{"type": "expression", "name": "happy"}'

# 动作控制
curl -X POST http://127.0.0.1:3000/api/live2d \
  -H "Content-Type: application/json" \
  -d '{"type": "action", "name": "wave"}'
```

### 聊天对话
```bash
# 发送文本消息
curl -X POST http://127.0.0.1:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"type": "user_message", "text": "你好", "sender": "user"}'
```

### 系统状态
```bash
# 获取系统状态
curl http://127.0.0.1:3000/api/system_status
```

## 🚧 已知限制

1. **浏览器兼容性**: 需要支持WebRTC和WebGL的现代浏览器
2. **音频延迟**: 网络环境可能影响音频传输延迟
3. **并发限制**: 当前版本不支持多用户同时访问
4. **移动端**: 移动浏览器可能存在音频权限问题

## 🔄 更新日志

### v4.0.0 (当前版本)
- ✅ 完成Zoev2 Live2D界面移植
- ✅ 集成Zoev3音频系统
- ✅ 实现Web语音录音功能（OPUS编码）
- ✅ 添加音频桥接服务
- ✅ 创建一键启动脚本
- ✅ 完善API接口设计
- ✅ 实现完整音频集成到主界面
- ✅ 支持53种情感映射到Live2D动作
- ✅ Web→小智AI语音对话完全可用

## 🤝 贡献指南

如需改进或添加功能：

1. 音频系统: 修改 `zoev3_audio_bridge.py`
2. Web界面: 编辑 `index.html` 和相关CSS/JS
3. 服务器API: 修改 `server.py`
4. Live2D控制: 调整 `emotion_mapping.py`

## 📞 技术支持

如遇到问题，请检查：
1. 所有依赖服务是否正常运行
2. 网络端口是否冲突
3. 浏览器控制台是否有错误信息
4. 系统日志是否有异常输出

---

🎉 **享受你的Zoev4 Web版本体验!** 🎉