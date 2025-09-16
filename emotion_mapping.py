#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情感映射配置
将小智AI的情感参数映射到Live2D的动作和表情
"""

from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from enum import Enum

@dataclass
class Live2DActionConfig:
    """Live2D动作配置"""
    action: str                    # 动作名称 (如: "kaixin", "idle", "talk")
    expression: Optional[str]      # 表情名称 (如: "love_eyes", "angry") 
    duration: float = 3.0          # 持续时间（秒）
    priority: int = 1              # 优先级 (1=低, 2=中, 3=高)
    description: str = ""          # 描述

class EmotionCategory(Enum):
    """情感类别"""
    POSITIVE = "positive"          # 积极情感
    NEGATIVE = "negative"          # 消极情感  
    NEUTRAL = "neutral"            # 中性情感
    ACTIVE = "active"              # 活跃状态
    THINKING = "thinking"          # 思考状态

class EmotionMapping:
    """情感映射管理器"""
    
    def __init__(self):
        """初始化情感映射表"""
        
        # 核心情感映射 - 基于小智AI标准emoji的21种情感类型
        self.emotion_map: Dict[str, Live2DActionConfig] = {

            # === 小智AI标准emoji映射 ===

            # 😶 - neutral
            "neutral": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=2.0,
                priority=1,
                description="中性平静的状态"
            ),

            # 🙂 - happy
            "happy": Live2DActionConfig(
                action="kaixin",
                expression="love_eyes",
                duration=4.0,
                priority=2,
                description="开心快乐的状态"
            ),

            # 😆 - laughing
            "laughing": Live2DActionConfig(
                action="kaixin",
                expression="star_eyes",
                duration=4.0,
                priority=2,
                description="大笑开怀的状态"
            ),

            # 😂 - funny
            "funny": Live2DActionConfig(
                action="kaixin",
                expression="tongue",
                duration=3.5,
                priority=2,
                description="搞笑幽默的状态"
            ),

            # 😔 - sad
            "sad": Live2DActionConfig(
                action="idle",
                expression="crying",
                duration=4.0,
                priority=2,
                description="悲伤难过的状态"
            ),

            # 😠 - angry
            "angry": Live2DActionConfig(
                action="shengqi",
                expression="angry",
                duration=3.5,
                priority=3,
                description="生气愤怒的状态"
            ),

            # 😭 - crying
            "crying": Live2DActionConfig(
                action="idle",
                expression="crying",
                duration=4.5,
                priority=3,
                description="哭泣痛苦的状态"
            ),

            # 😍 - loving
            "loving": Live2DActionConfig(
                action="kaixin",
                expression="love_eyes",
                duration=4.5,
                priority=3,
                description="爱意满满的状态"
            ),

            # 😳 - embarrassed
            "embarrassed": Live2DActionConfig(
                action="yaotou",
                expression=None,
                duration=3.0,
                priority=2,
                description="尴尬害羞的状态"
            ),

            # 😲 - surprised
            "surprised": Live2DActionConfig(
                action="jingya",
                expression="star_eyes",
                duration=2.5,
                priority=3,
                description="惊讶意外的状态"
            ),

            # 😱 - shocked
            "shocked": Live2DActionConfig(
                action="jingya",
                expression=None,
                duration=3.0,
                priority=3,
                description="震惊的状态"
            ),

            # 🤔 - thinking
            "thinking": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=3.0,
                priority=1,
                description="思考中的状态"
            ),

            # 😉 - winking
            "winking": Live2DActionConfig(
                action="wink",
                expression="tongue",
                duration=2.5,
                priority=2,
                description="眨眼调皮的状态"
            ),

            # 😎 - cool
            "cool": Live2DActionConfig(
                action="wink",
                expression=None,
                duration=3.0,
                priority=2,
                description="酷炫自信的状态"
            ),

            # 😌 - relaxed
            "relaxed": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=3.5,
                priority=1,
                description="放松舒缓的状态"
            ),

            # 🤤 - delicious
            "delicious": Live2DActionConfig(
                action="kaixin",
                expression="tongue",
                duration=3.0,
                priority=2,
                description="美味享受的状态"
            ),

            # 😘 - kissy
            "kissy": Live2DActionConfig(
                action="kaixin",
                expression="love_eyes",
                duration=3.5,
                priority=2,
                description="飞吻示爱的状态"
            ),

            # 😏 - confident
            "confident": Live2DActionConfig(
                action="wink",
                expression=None,
                duration=3.0,
                priority=2,
                description="自信得意的状态"
            ),

            # 😴 - sleepy
            "sleepy": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=4.0,
                priority=1,
                description="困倦疲惫的状态"
            ),

            # 😜 - silly
            "silly": Live2DActionConfig(
                action="wink",
                expression="tongue",
                duration=2.5,
                priority=2,
                description="调皮搞怪的状态"
            ),

            # 🙄 - confused
            "confused": Live2DActionConfig(
                action="yaotou",
                expression=None,
                duration=2.5,
                priority=2,
                description="困惑疑惑的状态"
            ),

            # === 兼容旧版映射 ===
            "joy": Live2DActionConfig(
                action="kaixin",
                expression="star_eyes",
                duration=3.5,
                priority=2,
                description="喜悦兴奋的状态"
            ),

            "excited": Live2DActionConfig(
                action="kaixin",
                expression="star_eyes",
                duration=3.0,
                priority=2,
                description="兴奋激动的状态"
            ),

            "love": Live2DActionConfig(
                action="kaixin",
                expression="love_eyes",
                duration=4.5,
                priority=3,
                description="爱意满满的状态"
            ),

            # === 扩展兼容映射（保持向后兼容） ===
            "disappointed": Live2DActionConfig(
                action="idle",
                expression="crying",
                duration=3.0,
                priority=2,
                description="失望沮丧的状态"
            ),

            "worried": Live2DActionConfig(
                action="yaotou",
                expression=None,
                duration=2.5,
                priority=2,
                description="担心忧虑的状态"
            ),

            "amazed": Live2DActionConfig(
                action="jingya",
                expression="star_eyes",
                duration=3.5,
                priority=2,
                description="惊叹赞叹的状态"
            ),

            "calm": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=2.5,
                priority=1,
                description="冷静平和的状态"
            ),

            "playful": Live2DActionConfig(
                action="wink",
                expression="tongue",
                duration=2.5,
                priority=2,
                description="顽皮搞怪的状态"
            ),

            "mischievous": Live2DActionConfig(
                action="wink",
                expression="tongue",
                duration=3.0,
                priority=2,
                description="淘气调皮的状态"
            ),

            "speaking": Live2DActionConfig(
                action="talk",
                expression=None,
                duration=5.0,  # 说话状态持续时间较长
                priority=3,    # 高优先级
                description="正在说话的状态"
            ),

            "greeting": Live2DActionConfig(
                action="kaixin",
                expression="love_eyes",
                duration=3.0,
                priority=2,
                description="打招呼问候的状态"
            ),

            "farewell": Live2DActionConfig(
                action="yaotou",
                expression=None,
                duration=2.5,
                priority=2,
                description="中性平静的状态"
            ),
            
            "calm": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=2.5,
                priority=1,
                description="冷静平和的状态"
            ),
            
            "thinking": Live2DActionConfig(
                action="idle",
                expression=None,
                duration=3.0,
                priority=1,
                description="思考中的状态"
            ),
            
            "confused": Live2DActionConfig(
                action="yaotou",
                expression=None,
                duration=2.5,
                priority=2,
                description="困惑疑惑的状态"
            ),
            
            # === 活跃状态 ===
            "playful": Live2DActionConfig(
                action="wink",
                expression="tongue",
                duration=2.5,
                priority=2,
                description="顽皮搞怪的状态"
            ),
            
            "mischievous": Live2DActionConfig(
                action="wink", 
                expression="tongue",
                duration=3.0,
                priority=2,
                description="淘气调皮的状态"
            ),
            
            # === 特殊状态 ===
            "speaking": Live2DActionConfig(
                action="talk",
                expression=None,
                duration=5.0,  # 说话状态持续时间较长
                priority=3,    # 高优先级
                description="正在说话的状态"
            ),
            
            "greeting": Live2DActionConfig(
                action="kaixin",
                expression="love_eyes",
                duration=3.0,
                priority=2,
                description="打招呼问候的状态"
            ),
            
            "farewell": Live2DActionConfig(
                action="yaotou",
                expression=None,
                duration=2.5,
                priority=2,
                description="告别再见的状态"
            )
        }
        
        # 情感类别分组 - 用于情感分析和统计
        self.emotion_categories = {
            EmotionCategory.POSITIVE: [
                "happy", "joy", "excited", "love", "playful", 
                "mischievous", "greeting", "amazed"
            ],
            EmotionCategory.NEGATIVE: [
                "sad", "angry", "disappointed", "worried"
            ],
            EmotionCategory.NEUTRAL: [
                "neutral", "calm", "thinking", "confused", "farewell"
            ],
            EmotionCategory.ACTIVE: [
                "excited", "playful", "mischievous", "surprised", "shocked"
            ],
            EmotionCategory.THINKING: [
                "thinking", "confused", "calm"
            ]
        }
        
        # 情感同义词映射 - 处理不同表达方式
        self.emotion_synonyms = {
            "glad": "happy",
            "cheerful": "happy", 
            "delighted": "joy",
            "thrilled": "excited",
            "upset": "sad",
            "mad": "angry",
            "furious": "angry",
            "startled": "surprised",
            "astonished": "amazed",
            "puzzled": "confused",
            "naughty": "mischievous",
            "funny": "playful"
        }
        
        # 默认情感配置
        self.default_emotion = Live2DActionConfig(
            action="idle",
            expression=None,
            duration=2.0,
            priority=1,
            description="默认待机状态"
        )
    
    def get_mapping(self, emotion: str) -> Live2DActionConfig:
        """
        获取情感对应的Live2D配置
        
        Args:
            emotion: 情感名称 (小写)
            
        Returns:
            Live2DActionConfig: 对应的动作配置
        """
        if not emotion:
            return self.default_emotion
            
        # 转换为小写
        emotion_lower = emotion.lower().strip()
        
        # 直接映射
        if emotion_lower in self.emotion_map:
            return self.emotion_map[emotion_lower]
        
        # 同义词映射
        if emotion_lower in self.emotion_synonyms:
            synonym = self.emotion_synonyms[emotion_lower]
            return self.emotion_map.get(synonym, self.default_emotion)
        
        # 未知情感，返回默认配置
        return self.default_emotion
    
    def get_emotion_category(self, emotion: str) -> Optional[EmotionCategory]:
        """获取情感类别"""
        emotion_lower = emotion.lower().strip()
        
        # 处理同义词
        if emotion_lower in self.emotion_synonyms:
            emotion_lower = self.emotion_synonyms[emotion_lower]
        
        # 查找类别
        for category, emotions in self.emotion_categories.items():
            if emotion_lower in emotions:
                return category
        
        return None
    
    def get_available_emotions(self) -> List[str]:
        """获取所有可用的情感列表"""
        emotions = list(self.emotion_map.keys())
        emotions.extend(self.emotion_synonyms.keys())
        return sorted(emotions)
    
    def get_emotions_by_category(self, category: EmotionCategory) -> List[str]:
        """获取指定类别的所有情感"""
        return self.emotion_categories.get(category, [])
    
    def validate_mapping(self) -> Dict[str, Any]:
        """验证映射表的完整性"""
        
        # 可用的Live2D动作
        available_actions = ["idle", "jingya", "kaixin", "shengqi", "wink", "yaotou", "talk"]
        
        # 可用的Live2D表情
        available_expressions = ["love_eyes", "angry", "star_eyes", "crying", "microphone", "coat", "tongue"]
        
        validation_result = {
            "total_emotions": len(self.emotion_map),
            "total_synonyms": len(self.emotion_synonyms),
            "invalid_actions": [],
            "invalid_expressions": [],
            "coverage_by_category": {},
            "priority_distribution": {},
            "is_valid": True
        }
        
        # 检查动作和表情的有效性
        for emotion, config in self.emotion_map.items():
            if config.action not in available_actions:
                validation_result["invalid_actions"].append(f"{emotion}: {config.action}")
                validation_result["is_valid"] = False
            
            if config.expression and config.expression not in available_expressions:
                validation_result["invalid_expressions"].append(f"{emotion}: {config.expression}")
                validation_result["is_valid"] = False
        
        # 统计各类别的覆盖情况
        for category in EmotionCategory:
            emotion_count = len(self.get_emotions_by_category(category))
            validation_result["coverage_by_category"][category.value] = emotion_count
        
        # 统计优先级分布
        priority_counts = {}
        for config in self.emotion_map.values():
            priority = config.priority
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        validation_result["priority_distribution"] = priority_counts
        
        return validation_result

# 全局情感映射实例
emotion_mapping = EmotionMapping()

def get_emotion_config(emotion: str) -> Live2DActionConfig:
    """快捷函数：获取情感配置"""
    return emotion_mapping.get_mapping(emotion)

def test_emotion_mapping():
    """测试情感映射功能"""
    print("🧪 情感映射表测试")
    print("=" * 50)
    
    # 测试基础映射
    test_emotions = ["happy", "sad", "angry", "surprised", "thinking", "speaking", "unknown"]
    
    print("📋 基础映射测试:")
    for emotion in test_emotions:
        config = get_emotion_config(emotion)
        print(f"   {emotion:<12} → action={config.action:<8} expression={config.expression or 'None':<10} ({config.description})")
    
    # 测试同义词
    print("\n📋 同义词映射测试:")
    synonyms = ["glad", "mad", "puzzled", "naughty"]
    for synonym in synonyms:
        config = get_emotion_config(synonym)
        print(f"   {synonym:<12} → action={config.action:<8} expression={config.expression or 'None':<10}")
    
    # 显示映射表验证结果
    print("\n📊 映射表验证:")
    validation = emotion_mapping.validate_mapping()
    print(f"   总情感数: {validation['total_emotions']}")
    print(f"   同义词数: {validation['total_synonyms']}")
    print(f"   映射有效: {'✅ 是' if validation['is_valid'] else '❌ 否'}")
    
    if validation['invalid_actions']:
        print(f"   ❌ 无效动作: {validation['invalid_actions']}")
    if validation['invalid_expressions']:
        print(f"   ❌ 无效表情: {validation['invalid_expressions']}")
    
    print(f"   类别覆盖: {validation['coverage_by_category']}")
    print(f"   优先级分布: {validation['priority_distribution']}")
    
    # 显示可用情感列表
    print(f"\n📝 支持的情感类型 ({len(emotion_mapping.get_available_emotions())} 种):")
    emotions = emotion_mapping.get_available_emotions()
    for i, emotion in enumerate(emotions):
        if i % 6 == 0:
            print("   ", end="")
        print(f"{emotion:<12}", end="")
        if (i + 1) % 6 == 0:
            print()
    print()

if __name__ == "__main__":
    test_emotion_mapping()