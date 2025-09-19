"""
小智AI表情自动监听器
完全无损入侵式设计，不修改现有代码逻辑
通过装饰器模式在数据流中插入监听功能
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class EmotionListener:
    """
    小智AI表情自动监听器

    设计原则：
    1. 完全无损入侵 - 不修改原有代码逻辑
    2. 插拔式设计 - 可随时启用/禁用
    3. 数据流透明 - 不影响原始数据传递
    4. 功能隔离 - 所有新功能独立在此模块
    """

    def __init__(self, gui_display_instance):
        """
        初始化表情监听器

        Args:
            gui_display_instance: GuiDisplay的实例
        """
        self.gui = gui_display_instance
        self._original_update_emotion = None
        self._is_listening = False
        self._emotion_stats = {}
        self._last_emotion_time = None

        # 小智AI标准21个emoji映射表
        self._emoji_mapping = {
            "😶": "neutral",     # 中性
            "🙂": "happy",       # 开心
            "😆": "laughing",    # 大笑
            "😂": "funny",       # 搞笑
            "😔": "sad",         # 悲伤
            "😠": "angry",       # 生气
            "😭": "crying",      # 哭泣
            "😍": "loving",      # 喜爱
            "😳": "embarrassed", # 尴尬
            "😲": "surprised",   # 惊讶
            "😱": "shocked",     # 震惊
            "🤔": "thinking",    # 思考
            "😉": "winking",     # 眨眼
            "😎": "cool",        # 酷炫
            "😌": "relaxed",     # 放松
            "🤤": "delicious",   # 美味
            "😘": "kissy",       # 飞吻
            "😏": "confident",   # 自信
            "😴": "sleepy",      # 困倦
            "😜": "silly",       # 调皮
            "🙄": "confused"     # 困惑
        }

        logger.info("🎭 表情监听器初始化完成")

    def start_listening(self):
        """
        启动监听器
        使用装饰器模式包装原有的update_emotion方法
        """
        if self._is_listening:
            logger.warning("⚠️ 表情监听器已经在运行中")
            return

        if not self._original_update_emotion:
            # 保存原始方法
            self._original_update_emotion = self.gui.update_emotion
            # 替换为增强版方法
            self.gui.update_emotion = self._enhanced_update_emotion

        self._is_listening = True
        logger.info("✅ 表情监听器已启动 - 开始监听小智AI表情数据")

    def stop_listening(self):
        """
        停止监听器
        恢复原始的update_emotion方法
        """
        if not self._is_listening:
            logger.warning("⚠️ 表情监听器未在运行")
            return

        if self._original_update_emotion:
            # 恢复原始方法
            self.gui.update_emotion = self._original_update_emotion

        self._is_listening = False
        logger.info("🛑 表情监听器已停止")

    async def _enhanced_update_emotion(self, emotion_name: str):
        """
        增强版update_emotion方法（异步版本）
        在不影响原有逻辑的前提下，加入自动化处理

        Args:
            emotion_name: 表情名称（可能是emoji或表情名）
        """
        try:
            # 先执行原有逻辑（完全不变）
            result = await self._original_update_emotion(emotion_name)

            # 然后执行额外的自动化处理
            self._process_xiaozhi_emotion(emotion_name)

            return result
        except Exception as e:
            logger.error(f"❌ 表情监听器处理失败: {e}")
            # 即使监听器出错，也要确保原有功能正常
            return await self._original_update_emotion(emotion_name)

    def _process_xiaozhi_emotion(self, emotion_name: str):
        """
        处理小智AI的表情数据
        在这里可以加入各种自动化逻辑

        Args:
            emotion_name: 表情名称或emoji
        """
        current_time = datetime.now()

        # 记录表情统计
        self._record_emotion_stats(emotion_name, current_time)

        # 智能表情识别
        emotion_info = self._analyze_emotion(emotion_name)

        # 日志记录（调试用）
        logger.info(f"🎭 监听到小智AI表情: {emotion_name} → {emotion_info}")

        # 可以在这里加入更多自动化功能：
        # - 表情历史记录
        # - 情感趋势分析
        # - 自动回应逻辑
        # - 外部API调用
        # - 数据统计上报

        self._last_emotion_time = current_time

    def _record_emotion_stats(self, emotion_name: str, timestamp: datetime):
        """
        记录表情统计数据

        Args:
            emotion_name: 表情名称
            timestamp: 时间戳
        """
        if emotion_name not in self._emotion_stats:
            self._emotion_stats[emotion_name] = {
                'count': 0,
                'first_seen': timestamp,
                'last_seen': timestamp
            }

        self._emotion_stats[emotion_name]['count'] += 1
        self._emotion_stats[emotion_name]['last_seen'] = timestamp

    def _analyze_emotion(self, emotion_name: str) -> Dict[str, Any]:
        """
        分析表情数据

        Args:
            emotion_name: 表情名称或emoji

        Returns:
            表情分析结果
        """
        analysis = {
            'input': emotion_name,
            'type': 'unknown',
            'mapped_emotion': None,
            'is_emoji': False,
            'category': 'unknown'
        }

        # 检查是否为emoji
        if emotion_name in self._emoji_mapping:
            analysis['type'] = 'emoji'
            analysis['is_emoji'] = True
            analysis['mapped_emotion'] = self._emoji_mapping[emotion_name]
        elif self._is_emoji_char(emotion_name):
            analysis['type'] = 'emoji'
            analysis['is_emoji'] = True
            analysis['mapped_emotion'] = 'unknown_emoji'
        else:
            analysis['type'] = 'emotion_name'
            analysis['mapped_emotion'] = emotion_name

        # 情感分类
        analysis['category'] = self._categorize_emotion(analysis['mapped_emotion'])

        return analysis

    def _is_emoji_char(self, text: str) -> bool:
        """
        检查字符串是否包含emoji

        Args:
            text: 待检查的文本

        Returns:
            是否包含emoji
        """
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "]+", flags=re.UNICODE
        )
        return bool(emoji_pattern.search(text))

    def _categorize_emotion(self, emotion: str) -> str:
        """
        对表情进行分类

        Args:
            emotion: 表情名称

        Returns:
            表情分类
        """
        if not emotion:
            return 'unknown'

        positive_emotions = ['happy', 'laughing', 'funny', 'loving', 'cool', 'confident', 'kissy', 'relaxed']
        negative_emotions = ['sad', 'angry', 'crying', 'embarrassed', 'shocked', 'confused']
        neutral_emotions = ['neutral', 'thinking', 'winking', 'sleepy', 'silly', 'surprised', 'delicious']

        if emotion in positive_emotions:
            return 'positive'
        elif emotion in negative_emotions:
            return 'negative'
        elif emotion in neutral_emotions:
            return 'neutral'
        else:
            return 'unknown'

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取表情统计数据

        Returns:
            统计数据字典
        """
        return {
            'is_listening': self._is_listening,
            'total_emotions': len(self._emotion_stats),
            'emotion_stats': dict(self._emotion_stats),
            'last_emotion_time': self._last_emotion_time,
            'supported_emojis': list(self._emoji_mapping.keys())
        }

    def reset_statistics(self):
        """重置统计数据"""
        self._emotion_stats.clear()
        self._last_emotion_time = None
        logger.info("🧹 表情统计数据已重置")

    def is_listening(self) -> bool:
        """检查监听器是否正在运行"""
        return self._is_listening