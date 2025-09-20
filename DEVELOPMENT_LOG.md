# Zoev4 Web端语音对话功能开发记录

## 开发目标
实现完整的Web端语音对话功能，将Zoev3客户端的音频播放转移到Web端播放。

## 核心问题
1. **音频播放问题**：AI回复的音频在Zoev3客户端播放，需要转到Web端播放
2. **聊天显示问题**：Web端没有显示用户语音转文字内容和AI回复内容

## 实现方案

### 1. 音频桥接服务修改 (`zoev3_audio_bridge.py`)

#### 新增功能：
- **Zoev3系统监听和拦截**：
  - 通过`setup_zoev3_monitoring()`方法拦截Zoev3的关键方法
  - 拦截`_handle_tts_message`、`_handle_stt_message`、`_handle_llm_response`方法
  - 拦截`_on_incoming_audio`方法阻止本地音频播放

- **消息转发功能**：
  - `broadcast_to_web_clients()`：转发STT、LLM、TTS消息到Web端
  - `broadcast_audio_to_web_clients()`：转发音频数据到Web端
  - 支持多个Web客户端同时连接

- **对话历史管理**：
  - 存储STT识别结果、LLM回复、TTS消息
  - 提供HTTP API查询和清除对话历史
  - 实时状态监控

#### 新增API端点：
- `GET /conversation/history`：获取对话历史
- `DELETE /conversation/history`：清除对话历史
- WebSocket消息类型：
  - `stt_result`：语音识别结果
  - `llm_response`：AI回复文本
  - `tts_message`：TTS状态消息
  - `audio_data`：音频播放数据

### 2. Web端界面修改 (`index.html`)

#### ZoeV4AudioClient类增强：
- **音频播放支持**：
  - `initAudioPlayback()`：初始化音频播放上下文
  - `handleAudioData()`：处理接收到的音频数据
  - `playAudioBuffer()`：播放解码后的音频
  - `playRawAudio()`：播放原始PCM音频数据

- **消息处理增强**：
  - `handleBridgeMessage()`：处理桥接器各种消息类型
  - `handleSTTResult()`：处理语音识别结果
  - `handleLLMResponse()`：处理AI回复
  - `handleTTSMessage()`：处理TTS播放状态

#### Live2D集成：
- STT识别时：Live2D播放idle动作
- LLM回复时：根据情感播放对应表情
- TTS开始时：Live2D播放talk动作
- TTS结束时：Live2D回到idle状态

#### 聊天界面功能：
- 自动显示用户语音转文字内容
- 自动显示AI回复文本
- 支持系统消息显示
- 自动滚动到最新消息

## 技术架构

```
用户 → Web端(录音) → 音频桥接服务 → Zoev3 → AI处理
                                      ↓
Web端(显示+播放) ← 音频桥接服务 ← Zoev3 ← AI回复
```

### 数据流：
1. **语音输入**：Web端 → 桥接器 → Zoev3
2. **语音识别**：Zoev3 → 桥接器 → Web端（显示文字）
3. **AI回复**：Zoev3 → 桥接器 → Web端（显示文字）
4. **语音合成**：Zoev3 → 桥接器 → Web端（播放音频）

## 关键特性

1. **实时音频流转发**：将Zoev3的TTS音频实时转发到Web端播放
2. **对话内容同步**：STT和LLM结果实时显示在Web聊天界面
3. **Live2D表情同步**：根据对话状态和AI情感自动更新Live2D表情
4. **多客户端支持**：支持多个Web客户端同时连接
5. **状态监控**：实时监控连接状态、消息处理统计

## 测试要点

1. **音频桥接测试**：
   - 启动`zoev3_audio_bridge.py`
   - 检查Zoev3监听设置是否成功
   - 验证WebSocket连接建立

2. **语音对话测试**：
   - Web端录音是否正常发送
   - STT结果是否正确显示
   - LLM回复是否正确显示
   - TTS音频是否在Web端播放
   - Live2D表情是否同步更新

3. **错误处理测试**：
   - 网络断开重连
   - 音频解码失败处理
   - 多客户端并发测试

## 文件修改总结

### `/Users/good/Desktop/Zoe-AI/Zoev4/zoev3_audio_bridge.py`
- 新增Zoev3监听拦截功能
- 新增消息转发功能
- 新增对话历史管理
- 新增HTTP API端点

### `/Users/good/Desktop/Zoe-AI/Zoev4/index.html`
- 增强ZoeV4AudioClient音频播放能力
- 新增多种消息处理方法
- 集成Live2D表情同步
- 完善聊天界面显示

## 下一步计划
- 测试完整的语音对话流程
- 优化音频播放质量和延迟
- 添加错误恢复机制
- 优化Live2D表情切换逻辑