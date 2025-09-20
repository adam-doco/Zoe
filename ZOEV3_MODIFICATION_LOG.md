# Zoev3 修改记录详细日志

## 📋 基本信息
- **修改日期**: 2025-09-19
- **修改目的**: 为Zoev3添加Web音频注入功能
- **备份位置**: `/Users/good/Desktop/Zoe-AI/Zoev3_BACKUP_20250919_162804`
- **修改人**: Claude (Zoev4项目)

## 🛡️ 安全措施已就位
- ✅ 完整备份已创建: `Zoev3_BACKUP_20250919_162804`
- ✅ 修改计划已制定: `ZOEV3_MODIFICATION_PLAN.md`
- ✅ 回退策略已准备
- ✅ 最小侵入性原则

---

## 📝 修改记录

### 修改 #1: AudioCodec类扩展
**文件**: `/Users/good/Desktop/Zoe-AI/Zoev3/src/audio_codecs/audio_codec.py`
**修改时间**: 2025-09-19 16:33
**修改类型**: 添加方法和功能
**备份文件**: `audio_codec.py.backup`

#### 修改前状态记录
```python
# 原始AudioCodec.__init__()方法末尾
def __init__(self):
    # ... 现有代码 ...
    self._is_closing = True  # 最后一行
```

#### 将要添加的代码位置
在`__init__()`方法中，`self._is_closing = False`之前添加：
```python
# Web音频注入功能 - Zoev4桥接支持
self._web_audio_enabled = False
self._web_audio_queue = asyncio.Queue(maxsize=100)
self._web_audio_monitor_task = None
```

#### 将要添加的新方法
在类的末尾添加：
```python
async def enable_web_audio_injection(self):
    """启用Web音频注入功能"""
    self._web_audio_enabled = True
    if not self._web_audio_monitor_task:
        self._web_audio_monitor_task = asyncio.create_task(
            self._monitor_web_audio_injection()
        )
    logger.info("✅ Web音频注入功能已启用")

async def inject_opus_audio(self, opus_data: bytes):
    """注入OPUS音频数据到处理队列"""
    if not self._web_audio_enabled:
        return False

    try:
        # 解码OPUS数据
        pcm_data = self.opus_decoder.decode(opus_data, len(opus_data))
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)

        # 加入处理队列
        await self._web_audio_queue.put(audio_array)
        logger.debug(f"💉 注入音频数据: {len(opus_data)} 字节")
        return True

    except Exception as e:
        logger.error(f"❌ 音频注入失败: {e}")
        return False

async def _monitor_web_audio_injection(self):
    """监控Web音频注入"""
    trigger_file = "/tmp/zoev4_audio_trigger"
    audio_file = "/tmp/zoev4_audio_injection.opus"
    last_check_time = 0

    while self._web_audio_enabled and not self._is_closing:
        try:
            if os.path.exists(trigger_file):
                trigger_time = float(open(trigger_file).read().strip())

                if trigger_time > last_check_time:
                    last_check_time = trigger_time

                    if os.path.exists(audio_file):
                        with open(audio_file, "rb") as f:
                            opus_data = f.read()

                        # 注入音频数据
                        await self.inject_opus_audio(opus_data)

                        # 清理文件
                        os.remove(audio_file)
                        os.remove(trigger_file)

                        logger.info(f"🎤 处理Web音频注入: {len(opus_data)} 字节")

            await asyncio.sleep(0.1)  # 100ms检查间隔

        except Exception as e:
            logger.warning(f"⚠️ Web音频监控错误: {e}")
            await asyncio.sleep(1)

async def _process_web_audio_queue(self):
    """处理Web音频队列中的数据"""
    while not self._web_audio_queue.empty():
        try:
            audio_data = self._web_audio_queue.get_nowait()

            # 将音频数据发送给编码回调（模拟麦克风输入）
            if self._encoded_audio_callback:
                # 转换为编码格式
                pcm_bytes = audio_data.astype(np.int16).tobytes()
                encoded_data = self.opus_encoder.encode(
                    pcm_bytes, len(audio_data)
                )

                if encoded_data:
                    self._encoded_audio_callback(encoded_data)
                    logger.debug("📤 Web音频数据已发送给py-xiaozhi")

        except asyncio.QueueEmpty:
            break
        except Exception as e:
            logger.error(f"❌ Web音频队列处理错误: {e}")
```

#### 修改现有方法
需要修改`_input_callback()`方法，在开头添加Web音频处理：
```python
def _input_callback(self, indata, frames, time_info, status):
    """
    录音回调，硬件驱动调用 处理流程：原始音频 -> 重采样16kHz -> 编码发送 + 唤醒词检测.
    """
    # 优先处理Web音频注入
    if self._web_audio_enabled:
        asyncio.create_task(self._process_web_audio_queue())

    # ... 原有代码保持不变 ...
```

#### 回退方法
```bash
# 恢复原始文件
cp /Users/good/Desktop/Zoe-AI/Zoev3/src/audio_codecs/audio_codec.py.backup \
   /Users/good/Desktop/Zoe-AI/Zoev3/src/audio_codecs/audio_codec.py
```

---

### 修改 #2: Application类集成
**文件**: `/Users/good/Desktop/Zoe-AI/Zoev3/src/application.py`
**修改时间**: 2025-09-19 16:33
**修改类型**: 添加Web音频桥接启动
**备份文件**: `application.py.backup`

#### 修改位置
在`async def initialize()`方法中，音频初始化之后添加：
```python
# 启用Web音频桥接功能
if self.audio_codec:
    await self.audio_codec.enable_web_audio_injection()
    logger.info("🌉 Web音频桥接功能已启用")
```

#### 回退方法
```bash
# 恢复原始文件
cp /Users/good/Desktop/Zoe-AI/Zoev3/src/application.py.backup \
   /Users/good/Desktop/Zoe-AI/Zoev3/src/application.py
```

---

## 📊 修改状态跟踪

### 计划修改文件列表
- [ ] `src/audio_codecs/audio_codec.py` - Web音频注入功能
- [ ] `src/application.py` - 集成桥接启动

### 备份文件列表
- [ ] `audio_codec.py.backup` - AudioCodec原始备份
- [ ] `application.py.backup` - Application原始备份

### 测试检查清单
#### 修改前基准测试
- [ ] Zoev3正常启动
- [ ] Live2D模型正常加载
- [ ] 表情系统正常工作
- [ ] 聊天功能正常
- [ ] 音频系统正常初始化

#### 修改后功能测试
- [ ] Zoev3仍能正常启动
- [ ] 原有功能未受影响
- [ ] Web音频注入监听已启动
- [ ] 能够接收并处理注入的音频文件
- [ ] 音频数据能正确传递给py-xiaozhi

#### 性能测试
- [ ] 启动时间对比
- [ ] 内存使用对比
- [ ] CPU使用对比
- [ ] 音频延迟测试

---

## 🚨 紧急回退程序

### 立即回退命令
```bash
#!/bin/bash
echo "🚨 执行Zoev3紧急回退..."

# 停止运行中的Zoev3进程
pkill -f "python.*main.py.*gui"

# 恢复所有修改的文件
cd /Users/good/Desktop/Zoe-AI/Zoev3/src/audio_codecs/
cp audio_codec.py.backup audio_codec.py

cd /Users/good/Desktop/Zoe-AI/Zoev3/src/
cp application.py.backup application.py

# 清理临时文件
rm -f /tmp/zoev4_audio_*

echo "✅ Zoev3已回退到修改前状态"
echo "可以重新启动Zoev3验证功能"
```

### 完整备份恢复
```bash
# 如果需要完全恢复，使用完整备份
rm -rf /Users/good/Desktop/Zoe-AI/Zoev3
cp -r /Users/good/Desktop/Zoe-AI/Zoev3_BACKUP_20250919_162804 \
      /Users/good/Desktop/Zoe-AI/Zoev3
```

---

## 📅 修改时间线

| 时间 | 操作 | 状态 | 备注 |
|------|------|------|------|
| 16:28 | 创建完整备份 | ✅ 完成 | Zoev3_BACKUP_20250919_162804 |
| 16:28 | 制定修改计划 | ✅ 完成 | 详细记录所有修改点 |
| [待定] | 开始修改AudioCodec | 🔄 待执行 | 最小侵入性原则 |
| [待定] | 测试修改结果 | 🔄 待执行 | 功能和性能验证 |
| [待定] | 用户验收测试 | 🔄 待执行 | 端到端音频测试 |

---

**重要提醒**:
1. 每个修改步骤都必须先备份原文件
2. 每次修改后立即测试基本功能
3. 如发现任何问题立即执行回退
4. 保持详细的修改记录更新

**当前状态**: 准备就绪，等待执行修改指令