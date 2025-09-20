# Zoev4 Web端语音对话系统

一个完整的Web端语音对话系统，支持实时语音识别、AI回复和TTS音频播放，集成Live2D虚拟角色。

## 功能特性

- 🎤 **实时语音录制**：基于WebRTC的高质量语音录制
- 🗣️ **语音识别显示**：实时显示用户语音转文字结果
- 🤖 **AI对话回复**：集成小智AI的智能对话回复
- 🔊 **Web端音频播放**：AI回复音频在Web端播放（而非客户端）
- 🎭 **Live2D表情同步**：根据对话状态自动更新虚拟角色表情
- 💬 **聊天界面**：完整的对话历史记录和实时显示

## 系统架构

```
用户 → Web界面 → 音频桥接服务 → Zoev3客户端 → AI服务
              ↑                    ↓
        聊天显示 ← 消息转发 ← AI回复/TTS音频
```

## 快速开始

### 1. 环境要求

- Python 3.8+
- Zoev3客户端正在运行
- 现代浏览器（支持WebRTC）

### 2. 启动服务

```bash
# 方法1: 使用启动脚本（推荐）
python start_web_voice_chat.py

# 方法2: 手动启动桥接服务
python zoev3_audio_bridge.py
```

### 3. 访问Web界面

打开浏览器访问：http://localhost:8004/

### 4. 开始对话

1. 点击语音按钮开始录音
2. 说话后松开按钮
3. 观察聊天界面显示识别结果
4. AI回复将自动显示和播放
5. Live2D角色会同步表情动作

## 监控和调试

### API端点

- **服务状态**：`GET http://localhost:8004/status`
- **对话历史**：`GET http://localhost:8004/conversation/history`
- **清除历史**：`DELETE http://localhost:8004/conversation/history`
- **音频测试**：`POST http://localhost:8004/inject-test`

### WebSocket消息类型

- `bridge_welcome`：桥接器连接成功
- `stt_result`：语音识别结果
- `llm_response`：AI回复文本
- `tts_message`：TTS播放状态
- `audio_data`：音频播放数据

## 技术细节

### 音频处理

- **录音格式**：16kHz单声道PCM
- **编码格式**：OPUS 60ms帧
- **播放支持**：Web Audio API
- **传输协议**：WebSocket二进制数据

### Live2D集成

- **待机状态**：录音结束后
- **说话动作**：AI回复播放时
- **表情同步**：根据AI情感标签
- **自动回归**：动作完成后自动返回待机

### 消息处理

- **实时转发**：Zoev3消息实时转发到Web端
- **状态同步**：TTS播放状态同步Live2D动作
- **历史记录**：完整的对话历史存储和查询

## 故障排除

### 常见问题

1. **无法连接桥接服务**
   - 检查Zoev3客户端是否运行
   - 确认端口8004未被占用
   - 查看控制台错误信息

2. **音频无法播放**
   - 确认浏览器支持Web Audio API
   - 检查音频权限设置
   - 查看浏览器控制台错误

3. **Live2D不显示**
   - 确认模型文件路径正确
   - 检查网络连接加载外部资源
   - 查看浏览器控制台错误

### 调试模式

启动时添加详细日志：

```bash
python zoev3_audio_bridge.py --debug
```

查看实时状态：

```bash
curl http://localhost:8004/status | jq
```

## 开发说明

### 文件结构

```
Zoev4/
├── zoev3_audio_bridge.py    # 音频桥接服务
├── index.html               # Web界面
├── start_web_voice_chat.py  # 启动脚本
├── DEVELOPMENT_LOG.md       # 开发记录
└── README_Web_Voice_Chat.md # 使用说明
```

### 核心组件

1. **Zoev3AudioBridge**：音频桥接服务类
2. **ZoeV4AudioClient**：Web端音频客户端
3. **Live2DManager**：Live2D角色管理
4. **消息处理系统**：实时消息转发和状态同步

## 许可证

本项目遵循MIT许可证。

## 支持

如有问题请查看：
- 开发日志：`DEVELOPMENT_LOG.md`
- 控制台输出
- 浏览器开发者工具