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
            # 读取现有队列
            with open(self.queue_file, 'r') as f:
                queue_data = json.load(f)
            
            # 添加新项目
            queue_item = {
                'data': item,
                'timestamp': time.time()
            }
            queue_data.append(queue_item)
            
            # 写回文件
            with open(self.queue_file, 'w') as f:
                json.dump(queue_data, f)
                
        except Exception as e:
            print(f"❌ 队列写入错误 ({self.name}): {e}")
    
    def get_nowait(self) -> Any:
        """立即获取队列项目，如果为空则抛出异常"""
        try:
            with open(self.queue_file, 'r') as f:
                queue_data = json.load(f)
            
            if not queue_data:
                raise queue.Empty("队列为空")
            
            # 获取第一项
            item = queue_data.pop(0)
            
            # 写回文件
            with open(self.queue_file, 'w') as f:
                json.dump(queue_data, f)
            
            return item['data']
            
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

# 创建跨进程共享队列
message_queue = FileBasedQueue("message_queue")      # 前端消息 → 消息处理器
ai_reply_queue = FileBasedQueue("ai_reply_queue")    # 消息处理器AI回复 → 前端
emotion_queue = FileBasedQueue("emotion_queue")      # 消息处理器情感数据 → emotion_controller
live2d_commands = FileBasedQueue("live2d_commands")  # Live2D控制命令队列

def get_queues():
    """获取所有队列"""
    return {
        'message_queue': message_queue,
        'ai_reply_queue': ai_reply_queue,
        'emotion_queue': emotion_queue,
        'live2d_commands': live2d_commands
    }

def clear_all_queues():
    """清空所有队列"""
    message_queue.clear()
    ai_reply_queue.clear()
    emotion_queue.clear()
    live2d_commands.clear()
    print("🧹 所有跨进程消息队列已清空")

def get_queue_status():
    """获取队列状态"""
    return {
        'message_queue_size': message_queue.qsize(),
        'ai_reply_queue_size': ai_reply_queue.qsize(),
        'emotion_queue_size': emotion_queue.qsize(),
        'live2d_commands_size': live2d_commands.qsize()
    }

if __name__ == "__main__":
    print("📨 跨进程消息队列模块")
    print("提供以下队列:")
    print("  - message_queue: 前端消息 → 消息处理器")
    print("  - ai_reply_queue: 消息处理器AI回复 → 前端")
    print("  - emotion_queue: 消息处理器情感数据 → emotion_controller")
    print("  - live2d_commands: Live2D控制命令队列")
    print("\n队列状态:", get_queue_status())