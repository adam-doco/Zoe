# Live2D 模型 API 调用文档

## 📋 概述

本文档描述了如何通过JavaScript API调用Live2D模型的状态和表情播放功能。

## 🚀 快速开始

### 基础用法

```javascript
// 播放状态
Live2DAPI.action.kaixin();  // 播放开心状态

// 播放表情
Live2DAPI.expression.love_eyes();  // 播放爱心眼表情

// 通用调用
Live2DAPI.call('action', 'idle');  // 播放待机状态
Live2DAPI.call('expression', 'angry');  // 播放生气表情
```

## 📡 API接口

### 🎭 状态控制 (Actions)

| API方法 | 说明 | 对应动作文件 |
|---------|------|-------------|
| `Live2DAPI.action.idle()` | 待机状态 | Idle.motion3.json |
| `Live2DAPI.action.jingya()` | 惊讶状态 | jingya.motion3.json |
| `Live2DAPI.action.kaixin()` | 开心状态 | kaixin.motion3.json |
| `Live2DAPI.action.shengqi()` | 生气状态 | shengqi.motion3.json |
| `Live2DAPI.action.wink()` | 眨眼状态 | wink.motion3.json |
| `Live2DAPI.action.yaotou()` | 摇头状态 | yaotou.motion3.json |
| `Live2DAPI.action.talk()` | 说话动作 | 多个嘴部参数智能动画 |

### 😊 表情控制 (Expressions)

| API方法 | 说明 | 对应表情文件 |
|---------|------|-------------|
| `Live2DAPI.expression.love_eyes()` | 爱心眼表情 | A1爱心眼.exp3.json |
| `Live2DAPI.expression.angry()` | 生气表情 | A2生气.exp3.json |
| `Live2DAPI.expression.star_eyes()` | 星星眼表情 | A3星星眼.exp3.json |
| `Live2DAPI.expression.crying()` | 哭哭表情 | A4哭哭.exp3.json |
| `Live2DAPI.expression.microphone()` | 麦克风表情 | B1麦克风.exp3.json |
| `Live2DAPI.expression.coat()` | 外套表情 | B2外套.exp3.json |
| `Live2DAPI.expression.tongue()` | 舌头表情 | 舌头.exp3.json |

### ✨ 说话动作特性

`Live2DAPI.action.talk()` 使用了先进的参数智能识别技术：

- **🔍 自动参数发现**: 扫描模型的所有168个参数，自动识别所有嘴部相关参数
- **🎭 多参数协同**: 同时控制多个嘴部参数，包括：
  - `ParamMouthForm`: 嘴形变化（周期性动画）
  - 开口参数: 嘴部张合动作（随机开合效果）
  - 其他嘴部参数: 细节补充动画
- **⏱️ 智能时序**: 3.2秒动画时长，80ms刷新间隔
- **🔄 状态恢复**: 动画结束后自动恢复所有参数的原始值
- **📊 详细日志**: 控制台输出所有发现的嘴部参数信息供调试

**技术实现**：
```javascript
// 动画会根据参数类型使用不同的动画模式
- Form类参数: mid + sin(step * 0.7) * range * 0.4
- Open类参数: min + sin(step * 0.8) * range * 0.8  
- 其他参数: mid + sin(step * 0.6) * range * 0.3
```

### 🔧 系统方法

#### 获取可用列表
```javascript
Live2DAPI.getAvailableList()
```

**返回值:**
```json
{
  "success": true,
  "data": {
    "actions": [
      {
        "id": "idle",
        "name": "待机",
        "description": "回到待机状态"
      },
      // ... 更多状态
    ],
    "expressions": [
      {
        "id": "love_eyes", 
        "name": "爱心眼",
        "description": "爱心形状的眼睛表情"
      },
      // ... 更多表情
    ]
  }
}
```

#### 获取系统状态
```javascript
Live2DAPI.getStatus()
```

**返回值:**
```json
{
  "success": true,
  "data": {
    "isLoaded": true,
    "version": "2.0.0",
    "timestamp": 1757702013845
  }
}
```

#### 通用调用方法
```javascript
Live2DAPI.call(type, name)
```

**参数:**
- `type`: 'action' | 'expression'
- `name`: 对应的动作或表情ID

**示例:**
```javascript
// 状态调用
Live2DAPI.call('action', 'idle');
Live2DAPI.call('action', 'kaixin'); 
Live2DAPI.call('action', 'talk');

// 表情调用  
Live2DAPI.call('expression', 'love_eyes');
Live2DAPI.call('expression', 'angry');
Live2DAPI.call('expression', 'star_eyes');
```

## 📊 响应格式

所有API调用都返回统一的响应格式：

### 成功响应
```json
{
  "success": true,
  "message": "播放开心状态",
  "action": "kaixin"  // 或 "expression": "love_eyes"
}
```

### 错误响应
```json
{
  "success": false,
  "message": "模型未加载完成",
  "error": "MODEL_NOT_READY"
}
```

### 错误代码

| 错误代码 | 说明 |
|----------|------|
| `SYSTEM_NOT_READY` | Live2D系统未初始化 |
| `MODEL_NOT_READY` | 模型未加载完成 |
| `UNKNOWN_ACTION` | 未知的状态名称 |
| `UNKNOWN_EXPRESSION` | 未知的表情名称 |
| `UNKNOWN_TYPE` | 未知的调用类型 |
| `EXECUTION_FAILED` | 执行失败 |

## 🎯 使用示例

### 1. 基本播放
```javascript
// 播放开心状态
Live2DAPI.action.kaixin();

// 播放爱心眼表情
Live2DAPI.expression.love_eyes();
```

### 2. 带错误处理的调用
```javascript
const result = Live2DAPI.action.kaixin();
if (result.success) {
    console.log('播放成功:', result.message);
} else {
    console.error('播放失败:', result.error);
}
```

### 3. 检查系统状态
```javascript
const status = Live2DAPI.getStatus();
if (status.data.isLoaded) {
    // 系统已就绪，可以调用API
    Live2DAPI.action.idle();
} else {
    console.log('Live2D系统未加载完成');
}
```

### 4. 获取所有可用的动作和表情
```javascript
const available = Live2DAPI.getAvailableList();
console.log('可用状态:', available.data.actions);
console.log('可用表情:', available.data.expressions);
```

### 5. 外部系统集成示例

```javascript
// 假设你有一个聊天机器人系统
function onChatbotResponse(emotion) {
    switch(emotion) {
        case 'happy':
            Live2DAPI.action.kaixin();
            Live2DAPI.expression.love_eyes();
            break;
        case 'sad':
            Live2DAPI.action.idle();
            Live2DAPI.expression.crying();
            break;
        case 'angry':
            Live2DAPI.action.shengqi();
            Live2DAPI.expression.angry();
            break;
        case 'speaking':
            Live2DAPI.action.talk();
            break;
    }
}

// 假设你有一个语音识别系统
function onSpeechStart() {
    Live2DAPI.action.talk();  // 开始说话动作
}

function onSpeechEnd() {
    Live2DAPI.action.idle();  // 回到待机状态
}
```

## ⚙️ 重要说明

### 状态特点
- 状态播放有时间限制，播放完成后会自动回到待机状态（除了待机状态本身）
- **说话状态**是特殊的嘴部参数动画，具有以下特点：
  - 自动识别模型中所有嘴部相关参数（ParamMouthForm等）
  - 根据参数类型智能选择动画模式（嘴形变化、开口动作等）
  - 3.2秒动画时长，适用于语音对话、TTS播放等场景
  - 动画结束后自动恢复原始嘴形状态

### 表情特点  
- 表情播放后会保持该表情状态，不会自动回归
- 如需重置表情，可以手动调用 `Live2DAPI.action.idle()` 回到待机状态

### 性能建议
- 不要过于频繁地调用API，建议间隔至少200ms
- 在播放新的状态或表情前，确保前一个动作已经开始播放

### 浏览器兼容性
- 支持所有现代浏览器（Chrome, Firefox, Safari, Edge）
- 需要JavaScript ES6+支持

## 🔗 技术支持

如需技术支持或有问题反馈，请通过控制台查看详细的错误信息：

```javascript
console.log('Live2D API状态:', Live2DAPI.getStatus());
console.log('可用功能列表:', Live2DAPI.getAvailableList());
```

---

**版本**: 2.0.0  
**更新时间**: 2025-01-13  
**兼容性**: Live2D Cubism 4.x