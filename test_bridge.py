#!/usr/bin/env python3
"""
Simple test bridge server to verify WebSocket communication between Live2D and PC client.
"""
import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestBridgeServer:
    def __init__(self, port: int = 8765):
        self.port = port
        self.clients = set()
        
    async def register_client(self, websocket: WebSocketServerProtocol):
        """注册新的客户端连接"""
        self.clients.add(websocket)
        logger.info(f"Client connected: {websocket.remote_address}, total clients: {len(self.clients)}")
        
    async def unregister_client(self, websocket: WebSocketServerProtocol):
        """注销客户端连接"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected: {websocket.remote_address}, total clients: {len(self.clients)}")
    
    async def broadcast_to_clients(self, message: dict):
        """向所有连接的客户端广播消息"""
        if not self.clients:
            logger.debug("No clients connected, skipping broadcast")
            return
            
        message_str = json.dumps(message, ensure_ascii=False)
        logger.info(f"Broadcasting to {len(self.clients)} clients: {message_str}")
        
        disconnected_clients = set()
        
        for client in self.clients:
            try:
                await client.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Client {client.remote_address} connection closed during broadcast")
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client.remote_address}: {e}")
                disconnected_clients.add(client)
        
        # 清理断开的连接
        for client in disconnected_clients:
            self.clients.discard(client)
    
    async def handle_client_message(self, websocket: WebSocketServerProtocol, message: str):
        """处理来自客户端的消息"""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            logger.info(f"Received message from client {websocket.remote_address}: {message_type}")
            
            if message_type == 'ping':
                # 响应心跳
                await websocket.send(json.dumps({'type': 'pong'}))
                logger.info("Sent pong response")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from client {websocket.remote_address}: {e}")
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
    
    async def client_handler(self, websocket, path=None):
        """处理客户端连接"""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {websocket.remote_address} disconnected")
        except Exception as e:
            logger.error(f"Error in client handler: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def start(self):
        """启动WebSocket服务器"""
        try:
            logger.info(f"Starting test bridge server on ws://localhost:{self.port}")
            self.server = await websockets.serve(
                self.client_handler,
                "localhost", 
                self.port,
                ping_interval=30,
                ping_timeout=10
            )
            logger.info(f"✓ Bridge server started successfully")
            return self.server
        except Exception as e:
            logger.error(f"Failed to start bridge server: {e}")
            raise
    
    async def simulate_tts_events(self):
        """模拟TTS事件发送"""
        await asyncio.sleep(3)  # 等待客户端连接
        
        if not self.clients:
            logger.warning("No clients connected for TTS simulation")
            return
        
        # 模拟LLM响应
        await self.broadcast_to_clients({
            'type': 'llm_response',
            'text': '你好，我是小智AI！这是一个测试消息。',
            'is_complete': True,
            'timestamp': asyncio.get_event_loop().time()
        })
        
        await asyncio.sleep(1)
        
        # 模拟TTS开始
        await self.broadcast_to_clients({
            'type': 'tts_event',
            'event': 'started',
            'timestamp': asyncio.get_event_loop().time()
        })
        
        await asyncio.sleep(3)
        
        # 模拟TTS完成
        await self.broadcast_to_clients({
            'type': 'tts_event',
            'event': 'completed',
            'timestamp': asyncio.get_event_loop().time()
        })
        
        logger.info("TTS simulation completed")

async def main():
    bridge = TestBridgeServer()
    server = await bridge.start()
    
    # 创建模拟TTS事件的任务
    tts_task = asyncio.create_task(bridge.simulate_tts_events())
    
    try:
        logger.info("Server running. Connect your browser to http://localhost:8000 and open index-bridge.html")
        logger.info("Press Ctrl+C to stop")
        
        # 等待服务器运行和TTS模拟任务
        await asyncio.gather(server.wait_closed(), tts_task)
        
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.close()
        await server.wait_closed()
        tts_task.cancel()
        logger.info("Server stopped")

if __name__ == "__main__":
    asyncio.run(main())