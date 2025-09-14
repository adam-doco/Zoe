#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的消息处理器
直接使用xiaozhi引擎，避免Live2D复杂性
"""

import asyncio
import time
import queue
import os
from xiaozhi import XiaozhiEngine
from shared_queues import message_queue, ai_reply_queue, emotion_queue

class SimpleMessageHandler:
    """简化的消息处理器"""
    
    def __init__(self):
        self.engine = None
        self.is_running = False
        self.processed_messages = 0
        self.connection_lost_flag = False  # 连接断开标记
        self.is_first_startup = True      # 首次启动标识

        # 心跳检测机制
        self.last_user_message_time = 0  # 最后用户消息时间
        self.heartbeat_timeout = 300.0   # 5分钟超时
        self.is_in_standby = True        # 启动时就是待机状态
        self.activation_requested = False # 激活请求标识

        # 激活信号文件路径
        self.activation_signal_file = "/tmp/xiaozhi_activation_request"

    async def initialize(self):
        """初始化系统但不连接小智AI"""
        print("🚀 启动简化消息处理器...")
        print("⏳ 系统进入待机状态，等待激活...")

        # 发送待机状态通知到前端
        self._send_standby_notification()

        # 系统启动完成，等待激活
        return True

    def _send_standby_notification(self):
        """发送待机状态通知到前端"""
        standby_notification = {
            'type': 'standby_status',
            'is_standby': True,
            'message': '系统处于待机状态，点击激活按钮连接',
            'timestamp': time.time()
        }
        ai_reply_queue.put(standby_notification)
        print("📤 已向前端发送待机状态通知")

    async def _create_xiaozhi_engine(self):
        """创建并初始化小智AI引擎"""
        print("🤖 初始化小智AI引擎...")

        self.engine = XiaozhiEngine()

        # 设置TTS回调来捕获AI回复
        def capture_ai_reply(state: str, text: str = None):
            if state == "sentence_start" and text:
                print(f"🤖 捕获AI回复: {text}")

                # 放入回复队列
                ai_reply_data = {
                    'type': 'ai_reply',
                    'text': text,
                    'timestamp': time.time(),
                    'emotion': 'neutral'
                }

                ai_reply_queue.put(ai_reply_data)
                print(f"✅ AI回复已放入队列: {text[:50]}...")

        # 设置音频回调来启用语音播放
        def capture_audio_data(audio_data: bytes):
            print(f"🎵 收到音频数据: {len(audio_data)} bytes - 启动播放")
            # 音频数据已经由xiaozhi.py自动播放，这里只做日志记录

        # 设置情感回调来捕获表情信息
        def capture_emotion(emotion: str):
            print(f"😊 捕获情感: {emotion}")

            # 创建情感数据
            emotion_data = {
                'type': 'emotion',
                'emotion': emotion,
                'timestamp': time.time()
            }

            # 放入情感专用队列，供emotion_controller获取
            emotion_queue.put(emotion_data)
            print(f"✅ 情感已放入emotion_queue: {emotion}")

            # 同时放入AI回复队列，供前端轮询获取
            ai_reply_queue.put(emotion_data)
            print(f"✅ 情感已放入ai_reply_queue: {emotion}")

        self.engine.on_tts = capture_ai_reply
        self.engine.on_audio_received = capture_audio_data
        self.engine.on_emotion = capture_emotion

        # 启动引擎
        print("🔗 连接小智AI...")
        boot_task = asyncio.create_task(
            self.engine.boot(force_new_device=False)
        )

        # 等待连接 - 使用更高频率检查以加快响应
        for i in range(60):  # 60次，每次0.2秒 = 最多12秒等待时间
            await asyncio.sleep(0.2)  # 减少到200ms检查间隔
            state = self.engine.get_current_state().value

            if state == "wsReady":
                print("✅ 小智AI连接成功")
                # 立即发送激活通知
                activation_notification = {
                    'type': 'standby_status',
                    'is_standby': False,
                    'message': '系统已激活，可以开始对话',
                    'timestamp': time.time()
                }
                ai_reply_queue.put(activation_notification)
                print(f"✅ 激活通知已发送到队列: is_standby={activation_notification['is_standby']}")
                break
            elif state == "error":
                print("❌ 小智AI连接错误")
                return False

            if i % 15 == 0:  # 每3秒输出一次状态（15 * 0.2 = 3秒）
                print(f"   状态: {state} ({(i+1)*0.2:.1f}s/12.0s)")
        else:
            print("⏰ 小智AI连接超时")
            return False

        print("🎉 小智AI引擎初始化成功")
        # 初始化心跳检测时间
        self.last_user_message_time = time.time()
        self.is_in_standby = False
        return True

    async def _check_heartbeat(self):
        """检查心跳超时并进入待机状态"""
        current_time = time.time()

        # 如果已经在待机状态，不需要重复检查
        if self.is_in_standby:
            return

        # 检查是否超过心跳超时时间
        if current_time - self.last_user_message_time > self.heartbeat_timeout:
            print(f"💤 用户超过{self.heartbeat_timeout}秒未活动，进入待机状态")
            await self._enter_standby_mode()

    def _check_activation_signal(self):
        """检查是否有激活信号文件"""
        if os.path.exists(self.activation_signal_file):
            try:
                print("📡 检测到激活信号文件")
                os.remove(self.activation_signal_file)  # 删除信号文件
                return True
            except Exception as e:
                print(f"⚠️ 处理激活信号文件时出错: {e}")
                return False
        return False

    async def _enter_standby_mode(self):
        """进入待机状态"""
        self.is_in_standby = True

        # 主动断开连接以节省资源
        if self.engine:
            try:
                print("🔌 主动断开小智AI连接以节省资源")
                await self.engine.cleanup()
                self.engine = None
            except Exception as e:
                print(f"⚠️ 断开连接时出错: {e}")

        # 向前端发送待机状态通知
        standby_notification = {
            'type': 'standby_status',
            'is_standby': True,
            'message': '系统已进入待机状态',
            'timestamp': time.time()
        }
        ai_reply_queue.put(standby_notification)
        print("📤 已向前端发送待机状态通知")

    async def request_activation(self):
        """请求激活重连（由API调用）"""
        if not self.is_in_standby:
            return {"status": "error", "message": "系统未处于待机状态"}

        print("🔄 收到激活请求，开始连接小智AI...")

        # 创建并初始化小智AI引擎
        success = await self._create_xiaozhi_engine()

        if success:
            print("✅ 激活成功，系统已恢复正常")

            # 发送激活成功通知
            activation_notification = {
                'type': 'standby_status',
                'is_standby': False,
                'message': '系统已激活，可以开始对话',
                'timestamp': time.time()
            }
            ai_reply_queue.put(activation_notification)
            return {"status": "success", "message": "激活成功"}
        else:
            print("❌ 激活失败")
            return {"status": "error", "message": "激活失败"}

    def get_system_status(self):
        """获取系统状态信息"""
        return {
            "is_standby": self.is_in_standby,
            "last_user_message_time": self.last_user_message_time,
            "heartbeat_timeout": self.heartbeat_timeout,
            "processed_messages": self.processed_messages
        }

    async def _full_reconnect(self):
        """按照py-xiaozhi方式进行完整重连"""
        print("🔄 开始完整重连流程...")

        try:
            # 1. 清理旧引擎
            if self.engine:
                print("🧹 清理旧引擎...")
                try:
                    await self.engine.cleanup()
                except:
                    pass
                self.engine = None

            # 2. 重新创建和初始化引擎（复用initialize逻辑）
            print("🔧 重新创建小智AI引擎...")
            self.engine = XiaozhiEngine()

            # 3. 重新设置TTS回调
            def capture_ai_reply(state: str, text: str = None):
                if state == "sentence_start" and text:
                    print(f"🤖 捕获AI回复: {text}")

                    ai_reply_data = {
                        'type': 'ai_reply',
                        'text': text,
                        'timestamp': time.time(),
                        'emotion': 'neutral'
                    }

                    ai_reply_queue.put(ai_reply_data)
                    print(f"✅ AI回复已放入队列: {text[:50]}...")

            self.engine.on_tts = capture_ai_reply

            # 4. 重新设置音频回调
            def capture_audio_data(audio_data: bytes):
                print(f"🎵 收到音频数据: {len(audio_data)} bytes - 启动播放")

            # 5. 重新设置情感回调
            def capture_emotion(emotion: str):
                print(f"😊 捕获情感: {emotion}")
                emotion_data = {
                    'type': 'emotion',
                    'emotion': emotion,
                    'timestamp': time.time()
                }

                # 放入情感专用队列，供emotion_controller获取
                emotion_queue.put(emotion_data)
                print(f"✅ 情感已放入emotion_queue: {emotion}")

                # 同时放入AI回复队列，供前端轮询获取
                ai_reply_queue.put(emotion_data)
                print(f"✅ 情感已放入ai_reply_queue: {emotion}")

            self.engine.on_audio_received = capture_audio_data
            self.engine.on_emotion = capture_emotion

            # 6. 重新启动引擎
            print("🚀 重新启动小智AI引擎...")
            boot_task = asyncio.create_task(
                self.engine.boot(force_new_device=False)
            )

            # 7. 等待连接就绪
            for i in range(30):  # 增加等待时间
                await asyncio.sleep(1)
                state = self.engine.get_current_state().value

                if state == "wsReady":
                    print("✅ 完整重连成功！小智AI已就绪")
                    self.connection_lost_flag = False  # 清除断开标记
                    self.is_in_standby = False  # 更新待机状态

                    # 发送激活通知给前端
                    activation_notification = {
                        'type': 'standby_status',
                        'is_standby': False,
                        'message': '系统已重连激活，可以继续对话',
                        'timestamp': time.time()
                    }
                    ai_reply_queue.put(activation_notification)
                    print(f"✅ 重连激活通知已发送到队列: is_standby={activation_notification['is_standby']}")
                    return True
                elif state == "error":
                    print("❌ 重连过程中出现错误")
                    return False

                if i % 10 == 0:
                    print(f"   重连状态: {state} ({i+1}/30)")

            print("⏰ 重连超时")
            return False

        except Exception as e:
            print(f"❌ 完整重连异常: {e}")
            return False
    
    async def start_processing(self):
        """开始处理消息"""
        print("🔄 开始消息处理循环...")
        self.is_running = True

        last_connection_check = 0
        connection_check_interval = 30.0  # 30秒检查一次连接状态
        last_heartbeat_check = 0
        heartbeat_check_interval = 10.0  # 10秒检查一次心跳

        while self.is_running:
            try:
                current_time = time.time()

                # 心跳检测 - 新增
                if current_time - last_heartbeat_check > heartbeat_check_interval:
                    await self._check_heartbeat()
                    last_heartbeat_check = current_time

                # 如果在待机状态，检查是否有首次消息需要自动激活或手动激活信号
                if self.is_in_standby:
                    # 检查激活信号文件
                    if self._check_activation_signal():
                        print("🔄 收到手动激活信号，开始连接...")
                        success = await self._create_xiaozhi_engine()
                        if success:
                            print("✅ 手动激活成功")
                            # 激活通知已由_create_xiaozhi_engine()发送
                            continue  # 继续处理消息
                        else:
                            print("❌ 手动激活失败")

                    # 检查消息队列中是否有首次用户消息
                    elif not message_queue.empty() and self.is_first_startup:
                        print("🚀 检测到首次用户消息，自动激活连接...")
                        self.is_first_startup = False

                        # 自动激活连接
                        success = await self._create_xiaozhi_engine()
                        if success:
                            print("✅ 首次启动自动激活成功")
                            # 激活通知已由_create_xiaozhi_engine()发送
                            continue  # 继续处理消息
                        else:
                            print("❌ 首次启动自动激活失败")

                    await asyncio.sleep(1)
                    continue

                # 定期检查连接状态 - 保持原有逻辑
                if current_time - last_connection_check > connection_check_interval:
                    if self.engine:
                        state = self.engine.get_current_state().value
                        if state == "error":
                            print("⚠️ 检测到小智AI连接错误，请检查网络状态")
                        elif state == "activated":
                            # 检测到连接断开，记录状态但不立即重连
                            if not self.connection_lost_flag:
                                print("📝 检测到连接断开(activated状态)，记录断开标记")
                                print("💡 将在用户下次发送消息时重新连接")
                                self.connection_lost_flag = True
                        elif state != "wsReady":
                            print(f"📡 小智AI连接状态: {state}")
                    last_connection_check = current_time

                # 检查消息队列
                if not message_queue.empty():
                    message_data = message_queue.get_nowait()
                    await self._process_message(message_data)

                await asyncio.sleep(0.1)

            except queue.Empty:
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

                # 更新心跳时间 - 用户有活动
                self.last_user_message_time = time.time()

                # 检查是否有连接断开标记，如果有则先重连
                if self.connection_lost_flag:
                    print("🔄 检测到连接断开标记，执行完整重连...")

                    # 使用完整重连方法
                    success = await self._full_reconnect()
                    if not success:
                        print("❌ 完整重连失败，无法发送消息")
                        return

                # 发送到小智AI
                await self.engine.send_text_message(text)
                self.processed_messages += 1

                print(f"✅ 消息已发送 (总计: {self.processed_messages}条)")

        except Exception as e:
            print(f"❌ 处理消息异常: {e}")
    
    async def run(self):
        """运行消息处理器"""
        try:
            if not await self.initialize():
                return False
            
            print("=" * 50)
            print("🎉 简化消息处理器已启动")
            print("📨 等待前端消息...")
            print("🤖 将转发给小智AI并捕获真实回复")
            print("🛑 按 Ctrl+C 退出")
            print("=" * 50)
            
            await self.start_processing()
            
        except KeyboardInterrupt:
            print("\n⛔ 收到中断信号")
            self.is_running = False
        except Exception as e:
            print(f"❌ 运行异常: {e}")
            return False
        finally:
            await self._cleanup()
    
    async def _cleanup(self):
        """清理资源"""
        print("🧹 清理资源...")
        self.is_running = False
        if self.engine:
            try:
                await self.engine.cleanup()
            except:
                pass

# 全局handler实例，供API调用
global_handler = None

async def main():
    global global_handler
    global_handler = SimpleMessageHandler()
    await global_handler.run()

if __name__ == "__main__":
    try:
        print("🚀 启动简化消息处理器...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 消息处理器已退出")