#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨进程共享队列模块
使用multiprocessing.Queue实现跨进程通信
"""

import multiprocessing as mp
import queue
import time
import pickle
import os
import tempfile
import json
import base64
import fcntl
from typing import Dict, Any, Optional

class FileBasedQueue:
    """基于文件的简单队列实现，支持跨进程"""
    
    def __init__(self, name: str):
        self.name = name
        self.queue_dir = os.path.join(tempfile.gettempdir(), "xiaozhi_queues")
        os.makedirs(self.queue_dir, exist_ok=True)
        self.queue_file = os.path.join(self.queue_dir, f"{name}.json")
        self._ensure_queue_file()
    
    def _ensure_queue_file(self):
        """确保队列文件存在"""
        if not os.path.exists(self.queue_file):
            with open(self.queue_file, 'w') as f:
                json.dump([], f)
    
    def put(self, item: Any):
        """放入队列"""
        try:
            # 使用文件锁防止并发写入冲突
            with open(self.queue_file, 'r+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取独占锁
                try:
                    f.seek(0)
                    content = f.read().strip()
                    if not content:
                        queue_data = []
                    else:
                        queue_data = json.loads(content)

                    # 处理包含bytes数据的情况
                    processed_item = self._encode_bytes_recursively(item)

                    # 添加新项目
                    queue_item = {
                        'data': processed_item,
                        'timestamp': time.time()
                    }
                    queue_data.append(queue_item)

                    # 写回文件
                    f.seek(0)
                    f.truncate()
                    json.dump(queue_data, f, indent=None, separators=(',', ':'))
                    f.flush()

                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁

        except Exception as e:
            print(f"❌ 队列写入错误 ({self.name}): {e}")
            # 如果文件损坏，重新创建
            try:
                self._ensure_queue_file()
                print(f"🔧 已重建损坏的队列文件: {self.name}")
            except:
                pass
    
    def get_nowait(self) -> Any:
        """立即获取队列项目，如果为空则抛出异常"""
        try:
            with open(self.queue_file, 'r+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取独占锁
                try:
                    f.seek(0)
                    content = f.read().strip()
                    if not content:
                        queue_data = []
                    else:
                        queue_data = json.loads(content)

                    if not queue_data:
                        raise queue.Empty("队列为空")

                    # 获取第一项
                    item = queue_data.pop(0)

                    # 写回文件
                    f.seek(0)
                    f.truncate()
                    json.dump(queue_data, f, indent=None, separators=(',', ':'))
                    f.flush()

                    # 处理可能包含base64编码bytes数据的情况
                    decoded_data = self._decode_bytes_recursively(item['data'])
                    return decoded_data

                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁

        except FileNotFoundError:
            self._ensure_queue_file()
            raise queue.Empty("队列为空")
        except Exception as e:
            print(f"❌ 队列读取错误 ({self.name}): {e}")
            raise queue.Empty("队列读取失败")
    
    def get(self) -> Any:
        """获取队列项目（与get_nowait相同，保持API兼容性）"""
        return self.get_nowait()
    
    def empty(self) -> bool:
        """检查队列是否为空"""
        try:
            with open(self.queue_file, 'r') as f:
                queue_data = json.load(f)
            return len(queue_data) == 0
        except:
            return True
    
    def qsize(self) -> int:
        """获取队列大小"""
        try:
            with open(self.queue_file, 'r') as f:
                queue_data = json.load(f)
            return len(queue_data)
        except:
            return 0
    
    def clear(self):
        """清空队列"""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump([], f)
        except Exception as e:
            print(f"❌ 清空队列错误 ({self.name}): {e}")

    def _encode_bytes_recursively(self, obj: Any) -> Any:
        """递归编码bytes数据为base64字符串"""
        if isinstance(obj, bytes):
            return {
                '_type': 'bytes_b64',
                '_data': base64.b64encode(obj).decode('utf-8')
            }
        elif isinstance(obj, dict):
            return {k: self._encode_bytes_recursively(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._encode_bytes_recursively(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._encode_bytes_recursively(item) for item in obj)
        else:
            return obj

    def _decode_bytes_recursively(self, obj: Any) -> Any:
        """递归解码base64字符串为bytes数据"""
        if isinstance(obj, dict):
            if obj.get('_type') == 'bytes_b64' and '_data' in obj:
                return base64.b64decode(obj['_data'].encode('utf-8'))
            else:
                return {k: self._decode_bytes_recursively(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._decode_bytes_recursively(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._decode_bytes_recursively(item) for item in obj)
        else:
            return obj

# 创建跨进程共享队列
message_queue = FileBasedQueue("message_queue")      # 前端消息 → 消息处理器
ai_reply_queue = FileBasedQueue("ai_reply_queue")    # 消息处理器AI回复 → 前端
emotion_queue = FileBasedQueue("emotion_queue")      # 消息处理器情感数据 → emotion_controller
live2d_commands = FileBasedQueue("live2d_commands")  # Live2D控制命令队列
audio_queue = FileBasedQueue("audio_queue")          # 前端音频 → 消息处理器

def get_queues():
    """获取所有队列"""
    return {
        'message_queue': message_queue,
        'ai_reply_queue': ai_reply_queue,
        'emotion_queue': emotion_queue,
        'live2d_commands': live2d_commands,
        'audio_queue': audio_queue
    }

def clear_all_queues():
    """清空所有队列"""
    message_queue.clear()
    ai_reply_queue.clear()
    emotion_queue.clear()
    live2d_commands.clear()
    audio_queue.clear()
    print("🧹 所有跨进程消息队列已清空")

def get_queue_status():
    """获取队列状态"""
    return {
        'message_queue_size': message_queue.qsize(),
        'ai_reply_queue_size': ai_reply_queue.qsize(),
        'emotion_queue_size': emotion_queue.qsize(),
        'live2d_commands_size': live2d_commands.qsize(),
        'audio_queue_size': audio_queue.qsize()
    }

if __name__ == "__main__":
    print("📨 跨进程消息队列模块")
    print("提供以下队列:")
    print("  - message_queue: 前端消息 → 消息处理器")
    print("  - ai_reply_queue: 消息处理器AI回复 → 前端")
    print("  - emotion_queue: 消息处理器情感数据 → emotion_controller")
    print("  - live2d_commands: Live2D控制命令队列")
    print("  - audio_queue: 前端音频 → 消息处理器")
    print("\n队列状态:", get_queue_status())