#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live2D + 小智AI 消息处理器
处理前端消息队列，与小智AI交互，返回真实回复
"""

import asyncio
import time
import queue
import sys
import os
from live2d_xiaozhi_client import Live2DXiaozhiClient

# 导入全局消息队列
from message_queues import message_queue, ai_reply_queue
print("✅ 已导入消息队列")

class Live2DMessageHandler:
    """Live2D消息处理器"""
    
    def __init__(self):
        self.client = None
        self.is_running = False
        self.processed_messages = 0
        
    async def initialize(self):
        """初始化Live2D客户端"""
        print("🤖 初始化Live2D + 小智AI客户端...")
        
        self.client = Live2DXiaozhiClient()
        
        # 初始化Live2D前端
        live2d_ready = await self.client.initialize_live2d()
        if not live2d_ready:
            print("❌ Live2D前端连接失败")
            return False
        print("✅ Live2D前端连接成功")
        
        # 连接小智AI
        print("🔗 连接小智AI...")
        boot_task = asyncio.create_task(
            self.client.boot(force_new_device=False)
        )
        
        # 等待连接
        for i in range(30):
            await asyncio.sleep(1)
            state = self.client.get_current_state().value
            
            if state == "wsReady":
                print("✅ 小智AI连接成功")
                break
            elif state == "error":
                print("❌ 小智AI连接错误")
                return False
                
            if i % 5 == 0:
                print(f"   状态: {state} ({i+1}/30)")
        else:
            print("⏰ 小智AI连接超时")
            return False
        
        # 设置自定义的TTS回调来捕获AI回复
        self._setup_ai_reply_capture()
        
        print("🎉 Live2D + 小智AI 系统就绪")
        return True
    
    def _setup_ai_reply_capture(self):
        """设置AI回复捕获"""
        original_tts_callback = self.client.on_tts
        
        def tts_with_reply_capture(state: str, text: str = None):
            # 调用原始回调
            if original_tts_callback:
                original_tts_callback(state, text)
            
            # 捕获AI回复文本
            if state == "sentence_start" and text:
                print(f"🤖 捕获到小智AI回复: {text}")
                
                # 将AI回复放入队列供前端获取
                ai_reply_data = {
                    'type': 'ai_reply',
                    'text': text,
                    'timestamp': time.time(),
                    'emotion': getattr(self.client, 'current_emotion', 'neutral')
                }
                
                ai_reply_queue.put(ai_reply_data)
                print(f"✅ AI回复已放入队列: {text[:30]}...")
        
        self.client.on_tts = tts_with_reply_capture
    
    async def start_message_processing(self):
        """开始消息处理循环"""
        print("🔄 开始消息处理循环...")
        self.is_running = True
        
        while self.is_running:
            try:
                # 检查消息队列
                if not message_queue.empty():
                    message_data = message_queue.get_nowait()
                    await self._process_message(message_data)
                
                # 短暂休眠，避免过度占用CPU
                await asyncio.sleep(0.1)
                
            except queue.Empty:
                # 队列为空，继续等待
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ 消息处理异常: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, message_data):
        """处理单个消息"""
        try:
            message_type = message_data.get('type')
            text = message_data.get('text', '')
            sender = message_data.get('sender', 'user')
            
            if message_type == 'user_message' and sender == 'user':
                print(f"📨 处理用户消息: {text}")
                
                # 发送消息到小智AI
                await self.client.send_user_message(text)
                self.processed_messages += 1
                
                print(f"✅ 消息已发送到小智AI (总计: {self.processed_messages}条)")
            else:
                print(f"⚠️ 未知消息类型或发送者: {message_type}, {sender}")
                
        except Exception as e:
            print(f"❌ 处理消息异常: {e}")
            import traceback
            traceback.print_exc()
    
    async def run(self):
        """运行消息处理器"""
        try:
            # 初始化系统
            if not await self.initialize():
                print("❌ 初始化失败")
                return False
            
            print("=" * 60)
            print("🎉 Live2D + 小智AI 消息处理器已启动")
            print("📨 等待前端消息...")
            print("🤖 将自动转发给小智AI并返回真实回复")
            print("🛑 按 Ctrl+C 退出")
            print("=" * 60)
            
            # 开始消息处理循环
            await self.start_message_processing()
            
        except KeyboardInterrupt:
            print("\n⛔ 收到中断信号")
            self.is_running = False
        except Exception as e:
            print(f"❌ 运行异常: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self._cleanup()
    
    async def _cleanup(self):
        """清理资源"""
        print("🧹 清理资源...")
        self.is_running = False
        if self.client:
            try:
                await self.client.cleanup()
            except:
                pass
        print("✅ 清理完成")

async def main():
    """主函数"""
    handler = Live2DMessageHandler()
    await handler.run()

if __name__ == "__main__":
    try:
        print("🚀 启动Live2D消息处理器...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 消息处理器已退出")
    except Exception as e:
        print(f"❌ 启动异常: {e}")