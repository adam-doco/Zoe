#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于py-xiaozhi架构的稳定消息处理器
实现心跳机制、自动重连、错误恢复
"""

import asyncio
import time
import queue
import logging
from typing import Optional, Dict, Any
from xiaozhi import XiaozhiEngine
from shared_queues import message_queue, ai_reply_queue

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ROBUST_HANDLER")

class RobustMessageHandler:
    """稳定的消息处理器 - 基于py-xiaozhi架构"""
    
    def __init__(self):
        self.engine: Optional[XiaozhiEngine] = None
        self.is_running = False
        self.processed_messages = 0
        self.failed_messages = 0
        
        # 连接状态管理
        self.is_connected = False
        self.last_heartbeat = 0
        self.connection_attempts = 0
        self.max_reconnect_attempts = 10
        
        # 自动重连配置
        self.auto_reconnect_enabled = True
        self.reconnect_delay = 1.0  # 初始重连延迟
        self.max_reconnect_delay = 30.0  # 最大重连延迟
        self.reconnect_factor = 1.5  # 指数退避因子
        
        # 心跳配置
        self.heartbeat_interval = 30.0  # 心跳间隔（延长）
        self.heartbeat_timeout = 90.0   # 心跳超时（延长）
        
        # 任务管理
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> bool:
        """初始化引擎和连接"""
        logger.info("🤖 初始化稳定消息处理器...")
        
        try:
            self.engine = XiaozhiEngine()
            
            # 设置回调来捕获AI回复、音频数据和情感信息
            self.engine.on_tts = self._capture_ai_reply
            self.engine.on_audio_received = self._capture_audio_data
            self.engine.on_emotion = self._capture_emotion
            
            # 首次连接
            if await self._connect():
                logger.info("✅ 初始化成功")
                return True
            else:
                logger.error("❌ 初始化失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 初始化异常: {e}")
            return False
    
    async def _connect(self) -> bool:
        """连接到小智AI"""
        try:
            logger.info("🔗 连接小智AI...")
            self.connection_attempts += 1
            
            # 如果引擎已存在，先清理
            if self.engine:
                try:
                    await self.engine.cleanup()
                    await asyncio.sleep(1)  # 等待清理完成
                except:
                    pass
            
            # 重新创建引擎
            self.engine = XiaozhiEngine()
            self.engine.on_tts = self._capture_ai_reply
            self.engine.on_audio_received = self._capture_audio_data
            self.engine.on_emotion = self._capture_emotion
            
            # 启动引擎
            boot_task = asyncio.create_task(
                self.engine.boot(force_new_device=False)
            )
            
            # 等待连接建立
            for i in range(30):  # 30秒超时
                await asyncio.sleep(1)
                state = self.engine.get_current_state().value
                
                if state == "wsReady":
                    self.is_connected = True
                    self.last_heartbeat = time.time()
                    self.connection_attempts = 0
                    self.reconnect_delay = 1.0  # 重置重连延迟
                    
                    logger.info("✅ 小智AI连接成功")
                    
                    # 启动心跳监控
                    await self._start_heartbeat()
                    return True
                    
                elif state == "error":
                    logger.error("❌ 小智AI连接错误")
                    return False
                    
                if i % 5 == 0:
                    logger.info(f"   状态: {state} ({i+1}/30)")
            
            logger.warning("⏰ 连接超时")
            return False
            
        except Exception as e:
            logger.error(f"❌ 连接异常: {e}")
            return False
    
    async def _start_heartbeat(self):
        """启动心跳监控"""
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
        
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("💓 启动心跳监控")
    
    async def _heartbeat_loop(self):
        """心跳循环监控"""
        while self.is_running and self.is_connected:
            try:
                current_time = time.time()
                
                # 检查心跳超时
                if current_time - self.last_heartbeat > self.heartbeat_timeout:
                    logger.warning("💔 心跳超时，连接可能已断开")
                    await self._handle_connection_lost()
                    break
                
                # 检查引擎状态
                if self.engine:
                    state = self.engine.get_current_state().value
                    if state != "wsReady":
                        logger.warning(f"🔄 状态变化: {state}")
                        if state == "error":
                            await self._handle_connection_lost()
                            break
                    else:
                        self.last_heartbeat = current_time
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                logger.info("💓 心跳监控已停止")
                break
            except Exception as e:
                logger.error(f"💔 心跳监控异常: {e}")
                await asyncio.sleep(5)
    
    async def _handle_connection_lost(self):
        """处理连接丢失"""
        logger.warning("🔌 检测到连接丢失")
        self.is_connected = False
        
        if self.auto_reconnect_enabled and self.is_running:
            await self._schedule_reconnect()
    
    async def _schedule_reconnect(self):
        """安排重连"""
        if self.connection_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ 超过最大重连次数 ({self.max_reconnect_attempts})")
            self.is_running = False
            return
        
        if self.reconnect_task and not self.reconnect_task.done():
            return  # 已有重连任务
        
        self.reconnect_task = asyncio.create_task(self._reconnect_with_backoff())
    
    async def _reconnect_with_backoff(self):
        """指数退避重连"""
        try:
            logger.info(f"⏳ {self.reconnect_delay:.1f}秒后重连 (第{self.connection_attempts}次)")
            await asyncio.sleep(self.reconnect_delay)
            
            if await self._connect():
                logger.info("🎉 重连成功")
            else:
                # 增加重连延迟（指数退避）
                self.reconnect_delay = min(
                    self.reconnect_delay * self.reconnect_factor,
                    self.max_reconnect_delay
                )
                await self._schedule_reconnect()
                
        except asyncio.CancelledError:
            logger.info("🔄 重连任务已取消")
        except Exception as e:
            logger.error(f"❌ 重连异常: {e}")
            await self._schedule_reconnect()
    
    def _capture_ai_reply(self, state: str, text: str = None):
        """捕获AI回复（文本和语音状态）"""
        try:
            if state == "sentence_start" and text:
                logger.info(f"🤖 捕获AI回复: {text[:50]}...")
                
                ai_reply_data = {
                    'type': 'ai_reply',
                    'text': text,
                    'timestamp': time.time(),
                    'emotion': 'neutral'
                }
                
                ai_reply_queue.put(ai_reply_data)
                logger.info(f"✅ AI回复已放入队列")
            
            # 捕获TTS状态变化，用于Live2D同步
            elif state in ['sentence_start', 'sentence_end', 'speak_start', 'speak_end']:
                tts_status_data = {
                    'type': 'tts_status',
                    'state': state,
                    'text': text,
                    'timestamp': time.time()
                }
                
                ai_reply_queue.put(tts_status_data)
                logger.debug(f"🗣️ TTS状态: {state}")
                
        except Exception as e:
            logger.error(f"❌ 捕获AI回复异常: {e}")
    
    def _capture_audio_data(self, audio_data: bytes):
        """捕获音频数据（xiaozhi.py已自动处理）"""
        pass  # xiaozhi.py已经完全处理音频，这里不需要任何操作
    
    def _capture_emotion(self, emotion: str):
        """捕获情感信息"""
        try:
            logger.info(f"😊 捕获情感: {emotion}")
            
            emotion_data = {
                'type': 'emotion',
                'emotion': emotion,
                'timestamp': time.time()
            }
            
            ai_reply_queue.put(emotion_data)
            logger.info(f"✅ 情感已放入队列: {emotion}")
            
        except Exception as e:
            logger.error(f"❌ 捕获情感异常: {e}")
    
    async def start_processing(self):
        """开始消息处理循环"""
        logger.info("🔄 开始消息处理循环...")
        self.is_running = True
        
        while self.is_running:
            try:
                # 检查连接状态
                if not self.is_connected:
                    await asyncio.sleep(1)
                    continue
                
                # 处理消息队列
                if not message_queue.empty():
                    message_data = message_queue.get_nowait()
                    await self._process_message_safe(message_data)
                
                await asyncio.sleep(0.1)
                
            except queue.Empty:
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"❌ 消息处理循环异常: {e}")
                await asyncio.sleep(1)
    
    async def _process_message_safe(self, message_data: Dict[str, Any]):
        """安全处理单个消息"""
        try:
            message_type = message_data.get('type')
            text = message_data.get('text', '')
            sender = message_data.get('sender', 'user')
            
            if message_type == 'user_message' and sender == 'user':
                logger.info(f"📨 处理用户消息: {text}")
                
                if not self.is_connected:
                    logger.warning("⚠️ 连接未就绪，消息暂存")
                    # 可以实现消息暂存队列
                    return
                
                # 检查引擎状态
                if not self.engine:
                    logger.error("❌ 引擎不存在")
                    await self._handle_connection_lost()
                    return
                
                current_state = self.engine.get_current_state().value
                if current_state != "wsReady":
                    logger.warning(f"⚠️ 引擎状态异常: {current_state}")
                    await self._handle_connection_lost()
                    return
                
                # 使用xiaozhi.py原生的文本消息发送方法
                result = await self.engine.send_text_message(text)
                
                # 检查发送结果
                if result is False:
                    logger.error("❌ 消息发送失败")
                    await self._handle_connection_lost()
                    return
                
                self.processed_messages += 1
                logger.info(f"✅ 消息已发送 (成功: {self.processed_messages}, 失败: {self.failed_messages})")
            
        except Exception as e:
            self.failed_messages += 1
            logger.error(f"❌ 处理消息异常: {e}")
            
            # 检查是否为连接相关错误
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["connection", "websocket", "1005", "1006", "1011"]):
                logger.warning("🔌 检测到连接相关错误，触发重连")
                await self._handle_connection_lost()
    
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            "is_running": self.is_running,
            "is_connected": self.is_connected,
            "processed_messages": self.processed_messages,
            "failed_messages": self.failed_messages,
            "connection_attempts": self.connection_attempts,
            "last_heartbeat": self.last_heartbeat,
            "current_time": time.time()
        }

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态（兼容server.py接口）"""
        return {
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "processed_messages": self.processed_messages,
            "failed_messages": self.failed_messages,
            "last_heartbeat": self.last_heartbeat,
            "connection_attempts": self.connection_attempts
        }
    
    async def run(self):
        """运行消息处理器"""
        try:
            if not await self.initialize():
                return False
            
            logger.info("=" * 60)
            logger.info("🎉 稳定消息处理器已启动")
            logger.info("📨 等待前端消息...")
            logger.info("🤖 自动重连、心跳监控已启用")
            logger.info("🛑 按 Ctrl+C 退出")
            logger.info("=" * 60)
            
            await self.start_processing()
            
        except KeyboardInterrupt:
            logger.info("\n⛔ 收到中断信号")
            self.is_running = False
        except Exception as e:
            logger.error(f"❌ 运行异常: {e}")
            return False
        finally:
            await self._cleanup()
    
    async def _cleanup(self):
        """清理资源"""
        logger.info("🧹 清理资源...")
        self.is_running = False
        self.auto_reconnect_enabled = False
        
        # 取消心跳任务
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 取消重连任务
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
        
        # 清理引擎
        if self.engine:
            try:
                await self.engine.cleanup()
            except:
                pass
        
        logger.info("✅ 清理完成")

# 创建全局实例供其他模块使用
global_handler = None

async def main():
    global global_handler
    handler = RobustMessageHandler()
    global_handler = handler  # 设置全局引用
    await handler.run()

if __name__ == "__main__":
    try:
        logger.info("🚀 启动稳定消息处理器...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 消息处理器已退出")