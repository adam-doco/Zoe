#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情感控制器 - 专门监听小智AI的情感输出并控制Live2D表情
"""

import asyncio
import time
import requests
import json
import logging
from shared_queues import emotion_queue

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("EMOTION_CTRL")

class EmotionController:
    """情感控制器"""
    
    def __init__(self):
        self.is_running = False
        self.processed_emotions = 0
        
        # Live2D API端点
        self.live2d_api_url = "http://localhost:3000/api/live2d"
        
        # 情感映射配置
        self.emotion_mapping = {
            'happy': {
                'expression': 'love_eyes',
                'action': 'kaixin',
                'description': '开心 - 爱心眼 + 开心动作'
            },
            'laughing': {
                'expression': 'tongue',
                'action': 'kaixin', 
                'description': '大笑 - 吐舌头 + 开心动作'
            },
            'cool': {
                'expression': 'star_eyes',
                'action': 'wink',
                'description': '酷 - 星星眼 + 眨眼动作'
            },
            'sad': {
                'expression': 'crying',
                'action': None,
                'description': '悲伤 - 哭泣表情'
            },
            'angry': {
                'expression': 'angry',
                'action': 'shengqi',
                'description': '生气 - 生气表情 + 生气动作'
            },
            'surprise': {
                'expression': None,
                'action': 'jingya',
                'description': '惊讶 - 惊讶动作'
            }
        }
    
    def call_live2d_api(self, api_type, name):
        """调用Live2D API"""
        try:
            # 直接调用前端的Live2D API接口
            frontend_url = "http://127.0.0.1:3000/api/live2d"
            
            payload = {
                'type': api_type,
                'name': name,
                'source': 'emotion_controller'
            }
            
            response = requests.post(
                frontend_url,
                json=payload,
                timeout=2
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Live2D命令发送成功: {api_type}.{name}")
                return True
            else:
                logger.warning(f"⚠️ Live2D命令发送失败: {response.status_code} (前端可能未启动)")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ 无法连接到前端 (前端可能未启动)")
            return False
        except Exception as e:
            logger.error(f"❌ Live2D API调用异常: {e}")
            return False
    
    def process_emotion(self, emotion_data):
        """处理情感数据"""
        try:
            emotion = emotion_data.get('emotion', '').lower()
            timestamp = emotion_data.get('timestamp', time.time())
            
            logger.info(f"🎭 处理情感: {emotion}")
            
            # 检查情感映射
            if emotion not in self.emotion_mapping:
                logger.warning(f"⚠️ 未知情感: {emotion}，使用默认开心表情")
                emotion = 'happy'
            
            mapping = self.emotion_mapping[emotion]
            logger.info(f"📋 情感映射: {mapping['description']}")
            
            # 先播放表情
            if mapping.get('expression'):
                success = self.call_live2d_api('expression', mapping['expression'])
                if not success:
                    logger.error(f"❌ 表情播放失败: {mapping['expression']}")
            
            # 再播放动作
            if mapping.get('action'):
                success = self.call_live2d_api('action', mapping['action'])
                if not success:
                    logger.error(f"❌ 动作播放失败: {mapping['action']}")

            # 不再自动播放talk动作，避免与前端重复
            # 前端会在收到AI回复文本时自动播放talk动作
            
            self.processed_emotions += 1
            logger.info(f"✅ 情感处理完成 (总计: {self.processed_emotions})")
            
        except Exception as e:
            logger.error(f"❌ 情感处理异常: {e}")
    
    async def start_monitoring(self):
        """开始监听情感队列"""
        logger.info("🎭 开始监听情感队列...")
        self.is_running = True
        
        while self.is_running:
            try:
                # 检查情感专用队列中的数据
                if not emotion_queue.empty():
                    data = emotion_queue.get_nowait()

                    # 处理情感数据（现在不需要类型检查，因为是专用队列）
                    if data.get('type') == 'emotion':
                        self.process_emotion(data)
                    else:
                        logger.warning(f"⚠️ emotion_queue中收到非情感数据: {data}")

                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ 监听异常: {e}")
                await asyncio.sleep(1)
    
    async def run(self):
        """运行情感控制器"""
        try:
            logger.info("=" * 60)
            logger.info("🎭 情感控制器启动")
            logger.info("📡 监听小智AI情感输出...")
            logger.info("🎨 控制Live2D模型表情和动作")
            logger.info("🛑 按 Ctrl+C 退出")
            logger.info("=" * 60)
            
            await self.start_monitoring()
            
        except KeyboardInterrupt:
            logger.info("\\n⛔ 收到中断信号")
            self.is_running = False
        except Exception as e:
            logger.error(f"❌ 运行异常: {e}")
            return False

async def main():
    controller = EmotionController()
    await controller.run()

if __name__ == "__main__":
    try:
        logger.info("🚀 启动情感控制器...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\\n👋 情感控制器已退出")