# Zoev3 修改计划 - Web音频注入支持

## ⚠️ 安全第一原则

**重要声明**: 本文档详细记录对Zoev3的所有修改，确保可以完全回退到原始状态。

## 📋 修改目标

为Zoev3添加Web音频注入功能，使其能够接收来自Zoev4桥接器的音频数据。

## 🛡️ 备份策略

### 1. 完整代码备份
```bash
# 创建Zoev3完整备份
cp -r /Users/good/Desktop/Zoe-AI/Zoev3 /Users/good/Desktop/Zoe-AI/Zoev3_BACKUP_$(date +%Y%m%d_%H%M%S)
```

### 2. 关键文件单独备份
需要修改的文件将逐个备份：
- `src/audio_codecs/audio_codec.py` → `audio_codec.py.backup`
- `src/application.py` → `application.py.backup`
- 其他涉及文件...

## 🎯 修改方案

### 方案选择: 最小侵入性修改

**原理**: 在现有AudioCodec基础上添加外部音频注入接口，不破坏原有逻辑。

### 核心修改点

#### 1. AudioCodec类扩展 (`src/audio_codecs/audio_codec.py`)

**修改内容**:
- 添加`enable_web_audio_injection()`方法
- 添加`inject_opus_audio(opus_data)`方法
- 添加外部音频队列`_web_audio_queue`
- 修改音频处理循环，优先处理注入音频

**修改位置**:
```python
# 在AudioCodec.__init__()中添加
self._web_audio_enabled = False
self._web_audio_queue = asyncio.Queue(maxsize=100)

# 添加新方法
async def enable_web_audio_injection(self):
    """启用Web音频注入功能"""

async def inject_opus_audio(self, opus_data: bytes):
    """注入OPUS音频数据"""

async def _check_web_audio_injection(self):
    """检查并处理注入的音频"""
```

#### 2. Application类集成 (`src/application.py`)

**修改内容**:
- 添加Web音频监听器
- 集成文件监控机制

**修改位置**:
```python
# 在Application.__init__()中添加
self._web_audio_monitor = None

# 添加方法
async def _setup_web_audio_bridge(self):
    """设置Web音频桥接"""

async def _monitor_web_audio_files(self):
    """监控Web音频文件注入"""
```

## 📝 详细修改记录

### 修改记录格式
```
文件: [文件路径]
修改时间: [时间戳]
修改类型: [添加/修改/删除]
修改位置: [行号或方法名]
修改内容: [具体修改]
回退方法: [如何撤销此修改]
测试状态: [测试结果]
```

## 🔄 回退策略

### 自动回退脚本
```bash
#!/bin/bash
# zoev3_rollback.sh
echo "开始回退Zoev3修改..."

# 恢复备份文件
cp /path/to/backup/audio_codec.py.backup /Users/good/Desktop/Zoe-AI/Zoev3/src/audio_codecs/audio_codec.py

# 删除新增文件
rm -f /Users/good/Desktop/Zoe-AI/Zoev3/src/web_audio_bridge.py

echo "Zoev3已恢复到修改前状态"
```

### 手动回退检查清单
- [ ] 恢复audio_codec.py原始内容
- [ ] 恢复application.py原始内容
- [ ] 删除所有新增的Web音频相关文件
- [ ] 验证Zoev3正常启动和运行
- [ ] 确认所有原有功能正常

## 🧪 测试策略

### 修改前测试
1. 记录当前Zoev3所有功能状态
2. 验证Live2D、表情、聊天等功能正常
3. 记录启动时间和资源使用

### 修改后测试
1. 验证Web音频注入功能
2. 确认原有功能未受影响
3. 性能对比测试

### 回退测试
1. 执行回退操作
2. 验证系统恢复到修改前状态
3. 确认无残留文件或配置

## 📊 风险评估

| 风险等级 | 风险描述 | 缓解措施 |
|---------|----------|----------|
| 🟢 低 | 新增代码bug | 完整测试，异常处理 |
| 🟡 中 | 影响原有功能 | 最小侵入，保持原逻辑 |
| 🔴 高 | 系统无法启动 | 完整备份，快速回退 |

## ✅ 执行检查清单

### 修改前准备
- [ ] 创建完整Zoev3备份
- [ ] 记录当前系统状态
- [ ] 准备回退脚本
- [ ] 确认修改方案

### 修改过程
- [ ] 逐文件修改并备份
- [ ] 实时记录修改详情
- [ ] 每次修改后测试
- [ ] 验证功能正常

### 修改后验证
- [ ] 完整功能测试
- [ ] 性能对比验证
- [ ] 文档更新
- [ ] 用户验收测试

---

**重要提醒**: 任何对Zoev3的修改都必须严格按照此计划执行，确保系统安全和可回退性。