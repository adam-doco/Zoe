#!/usr/bin/env python3
"""
小智AI桥接测试服务器 - 模拟真实的小智AI交互
"""
import asyncio
import json
import logging
import websockets
import random
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XiaozhiAIBridge:
    def __init__(self, port: int = 8765):
        self.port = port
        self.clients = set()
        self.server = None
        
    async def register_client(self, websocket):
        """注册新的客户端连接"""
        self.clients.add(websocket)
        logger.info(f"客户端连接: {websocket.remote_address}, 总客户端: {len(self.clients)}")
        
    async def unregister_client(self, websocket):
        """注销客户端连接"""
        self.clients.discard(websocket)
        logger.info(f"客户端断开: {websocket.remote_address}, 总客户端: {len(self.clients)}")
    
    async def broadcast_to_clients(self, message: dict):
        """向所有连接的客户端广播消息"""
        if not self.clients:
            logger.debug("无客户端连接，跳过广播")
            return
            
        message_str = json.dumps(message, ensure_ascii=False)
        logger.info(f"广播消息给 {len(self.clients)} 个客户端: {message['type']}")
        
        disconnected_clients = set()
        
        for client in self.clients:
            try:
                await client.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"客户端 {client.remote_address} 连接已关闭")
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"广播错误到 {client.remote_address}: {e}")
                disconnected_clients.add(client)
        
        # 清理断开的连接
        for client in disconnected_clients:
            self.clients.discard(client)
    
    async def handle_client_message(self, websocket, message: str):
        """处理来自客户端的消息"""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            logger.info(f"收到客户端消息: {message_type}")
            
            if message_type == 'ping':
                # 响应心跳
                await websocket.send(json.dumps({'type': 'pong'}))
                
            elif message_type == 'voice_start':
                # 开始录音 - 模拟开始监听
                await self.broadcast_to_clients({
                    'type': 'listening_state',
                    'is_listening': True,
                    'mode': 'manual',
                    'timestamp': time.time()
                })
                logger.info("🎤 开始监听用户语音")
                
            elif message_type == 'voice_end':
                # 结束录音 - 模拟整个AI对话流程
                await self.simulate_ai_conversation()
                
        except json.JSONDecodeError as e:
            logger.error(f"无效JSON: {e}")
        except Exception as e:
            logger.error(f"处理消息错误: {e}")
    
    async def simulate_ai_conversation(self):
        """模拟完整的AI对话流程"""
        
        # 1. 停止监听
        await self.broadcast_to_clients({
            'type': 'listening_state',
            'is_listening': False,
            'timestamp': time.time()
        })
        logger.info("🔇 停止监听")
        
        await asyncio.sleep(0.5)
        
        # 2. 模拟STT识别结果
        user_messages = [
            "你好小智，今天天气怎么样？",
            "给我讲个笑话吧",
            "现在几点了？",
            "播放一首音乐",
            "设置明天早上8点的闹钟",
            "帮我搜索最新的科技新闻"
        ]
        
        user_text = random.choice(user_messages)
        await self.broadcast_to_clients({
            'type': 'stt_result',
            'text': user_text,
            'is_final': True,
            'timestamp': time.time()
        })
        logger.info(f"👤 用户说: {user_text}")
        
        await asyncio.sleep(1)
        
        # 3. 模拟LLM响应
        ai_responses = {
            "你好小智，今天天气怎么样？": "你好！今天是晴天，温度大约22度，很适合出门活动呢！",
            "给我讲个笑话吧": "好的！为什么程序员更喜欢用暗色主题？因为光明会吸引bug！哈哈哈~",
            "现在几点了？": f"现在是{time.strftime('%H:%M')}，希望能帮到你！",
            "播放一首音乐": "好的，正在为您播放轻松的背景音乐，希望您喜欢！",
            "设置明天早上8点的闹钟": "好的，我已经为您设置了明天早上8点的闹钟，记得按时起床哦！",
            "帮我搜索最新的科技新闻": "我找到了一些最新的科技新闻：人工智能技术持续突破，量子计算研究取得新进展..."
        }
        
        ai_text = ai_responses.get(user_text, f"我听到了您说的'{user_text}'，这是一个很有趣的问题！让我想想该怎么回答...")
        
        await self.broadcast_to_clients({
            'type': 'llm_response',
            'text': ai_text,
            'is_complete': True,
            'timestamp': time.time()
        })
        logger.info(f"🤖 小智回复: {ai_text}")
        
        await asyncio.sleep(1)
        
        # 4. 模拟TTS开始
        await self.broadcast_to_clients({
            'type': 'tts_event',
            'event': 'started',
            'timestamp': time.time()
        })
        logger.info("🔊 TTS开始播放")
        
        # 5. 模拟TTS播放时间 (根据文本长度)
        play_duration = max(2, len(ai_text) * 0.1)  # 大约每10个字符1秒
        await asyncio.sleep(play_duration)
        
        # 6. 模拟TTS完成
        await self.broadcast_to_clients({
            'type': 'tts_event',
            'event': 'completed',
            'timestamp': time.time()
        })
        logger.info("✅ TTS播放完成")
        
        # 7. 会话完成
        await self.broadcast_to_clients({
            'type': 'session_event',
            'event': 'completed',
            'timestamp': time.time()
        })
    
    async def client_handler(self, websocket, path=None):
        """处理客户端连接"""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {websocket.remote_address} 已断开")
        except Exception as e:
            logger.error(f"客户端处理错误: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def start(self):
        """启动WebSocket服务器"""
        try:
            logger.info(f"🚀 启动小智AI桥接服务器 ws://localhost:{self.port}")
            self.server = await websockets.serve(
                self.client_handler,
                "localhost",
                self.port,
                ping_interval=30,
                ping_timeout=10
            )
            logger.info(f"✅ 小智AI桥接服务器启动成功！")
            return self.server
        except Exception as e:
            logger.error(f"❌ 启动服务器失败: {e}")
            raise
    
    async def demo_conversation(self):
        """演示对话（如果没有客户端时自动运行）"""
        await asyncio.sleep(5)  # 等待客户端连接
        
        if not self.clients:
            logger.info("⚠️  没有客户端连接，跳过演示")
            return
            
        logger.info("🎭 开始演示对话...")
        
        # 模拟一次完整对话
        await self.broadcast_to_clients({
            'type': 'listening_state',
            'is_listening': True,
            'mode': 'auto',
            'timestamp': time.time()
        })
        
        await asyncio.sleep(2)
        await self.simulate_ai_conversation()

async def main():
    bridge = XiaozhiAIBridge()
    server = await bridge.start()
    
    # 创建演示任务
    demo_task = asyncio.create_task(bridge.demo_conversation())
    
    try:
        logger.info("🌟 小智AI桥接服务器运行中...")
        logger.info("📱 请打开浏览器访问: http://localhost:8001/index-bridge-v2.html")
        logger.info("⏹️  按 Ctrl+C 停止服务器")
        
        # 等待服务器运行
        await asyncio.gather(server.wait_closed(), demo_task)
        
    except KeyboardInterrupt:
        logger.info("🛑 正在关闭服务器...")
        server.close()
        await server.wait_closed()
        demo_task.cancel()
        logger.info("👋 服务器已停止")

if __name__ == "__main__":
    asyncio.run(main())