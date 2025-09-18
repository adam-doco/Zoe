#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表情调试和监控工具
用于跟踪和分析表情触发的全过程
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from threading import Lock
from collections import deque

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class EmotionEvent:
    """表情事件记录"""
    timestamp: float
    event_type: str  # "received", "mapped", "triggered", "error"
    source_data: str  # 原始数据（emoji或emotion名称）
    processed_data: str  # 处理后的数据
    processing_time_ms: float
    success: bool
    error_message: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


class EmotionDebugger:
    """表情调试器 - 用于监控表情触发的完整流程"""

    def __init__(self, max_events: int = 1000):
        """
        初始化表情调试器

        Args:
            max_events: 最大保存的事件数量
        """
        self.max_events = max_events
        self._events = deque(maxlen=max_events)
        self._lock = Lock()

        # 统计信息
        self._stats = {
            "total_events": 0,
            "successful_triggers": 0,
            "failed_triggers": 0,
            "emoji_to_emotion_mappings": 0,
            "processing_times": deque(maxlen=100),  # 最近100次的处理时间
            "error_counts": {},
            "source_types": {"emoji": 0, "emotion": 0, "text": 0}
        }

        logger.info("🐛 表情调试器已初始化")

    def log_emotion_received(self, source_data: str, source_type: str = "unknown"):
        """记录表情数据接收事件"""
        with self._lock:
            event = EmotionEvent(
                timestamp=time.time(),
                event_type="received",
                source_data=source_data,
                processed_data="",
                processing_time_ms=0.0,
                success=True,
                additional_info={"source_type": source_type}
            )
            self._add_event(event)
            self._stats["source_types"][source_type] = self._stats["source_types"].get(source_type, 0) + 1

    def log_emotion_mapped(self, source_data: str, processed_data: str, processing_time_ms: float):
        """记录表情映射事件"""
        with self._lock:
            event = EmotionEvent(
                timestamp=time.time(),
                event_type="mapped",
                source_data=source_data,
                processed_data=processed_data,
                processing_time_ms=processing_time_ms,
                success=True
            )
            self._add_event(event)
            if source_data != processed_data:
                self._stats["emoji_to_emotion_mappings"] += 1

    def log_emotion_triggered(self, emotion_name: str, processing_time_ms: float, success: bool = True):
        """记录表情触发事件"""
        with self._lock:
            event = EmotionEvent(
                timestamp=time.time(),
                event_type="triggered",
                source_data=emotion_name,
                processed_data=emotion_name,
                processing_time_ms=processing_time_ms,
                success=success
            )
            self._add_event(event)

            # 更新统计信息
            if success:
                self._stats["successful_triggers"] += 1
            else:
                self._stats["failed_triggers"] += 1

            self._stats["processing_times"].append(processing_time_ms)

    def log_emotion_error(self, source_data: str, error_message: str, processing_time_ms: float = 0.0):
        """记录表情处理错误事件"""
        with self._lock:
            event = EmotionEvent(
                timestamp=time.time(),
                event_type="error",
                source_data=source_data,
                processed_data="",
                processing_time_ms=processing_time_ms,
                success=False,
                error_message=error_message
            )
            self._add_event(event)

            # 更新错误统计
            self._stats["error_counts"][error_message] = self._stats["error_counts"].get(error_message, 0) + 1
            self._stats["failed_triggers"] += 1

    def _add_event(self, event: EmotionEvent):
        """添加事件到队列"""
        self._events.append(event)
        self._stats["total_events"] += 1

    def get_recent_events(self, count: int = 10) -> List[EmotionEvent]:
        """获取最近的事件记录"""
        with self._lock:
            return list(self._events)[-count:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()

            # 计算平均处理时间
            if stats["processing_times"]:
                stats["avg_processing_time_ms"] = sum(stats["processing_times"]) / len(stats["processing_times"])
                stats["max_processing_time_ms"] = max(stats["processing_times"])
                stats["min_processing_time_ms"] = min(stats["processing_times"])
            else:
                stats["avg_processing_time_ms"] = 0.0
                stats["max_processing_time_ms"] = 0.0
                stats["min_processing_time_ms"] = 0.0

            # 计算成功率
            total_triggers = stats["successful_triggers"] + stats["failed_triggers"]
            stats["success_rate"] = (stats["successful_triggers"] / total_triggers * 100) if total_triggers > 0 else 0.0

            return stats

    def print_debug_report(self):
        """打印调试报告"""
        stats = self.get_statistics()
        recent_events = self.get_recent_events(5)

        print("\n" + "="*60)
        print("🎭 表情系统调试报告")
        print("="*60)
        print(f"📊 总事件数: {stats['total_events']}")
        print(f"✅ 成功触发: {stats['successful_triggers']}")
        print(f"❌ 失败触发: {stats['failed_triggers']}")
        print(f"📈 成功率: {stats['success_rate']:.1f}%")
        print(f"🔄 emoji映射次数: {stats['emoji_to_emotion_mappings']}")

        print(f"\n⏱️ 处理时间统计:")
        print(f"   平均: {stats['avg_processing_time_ms']:.2f}ms")
        print(f"   最大: {stats['max_processing_time_ms']:.2f}ms")
        print(f"   最小: {stats['min_processing_time_ms']:.2f}ms")

        print(f"\n📥 数据源统计:")
        for source_type, count in stats['source_types'].items():
            print(f"   {source_type}: {count}")

        if stats['error_counts']:
            print(f"\n❌ 错误统计:")
            for error, count in stats['error_counts'].items():
                print(f"   {error}: {count}")

        print(f"\n📋 最近事件:")
        for i, event in enumerate(recent_events, 1):
            status = "✅" if event.success else "❌"
            print(f"   {i}. {status} {event.event_type}: {event.source_data} → {event.processed_data} "
                  f"({event.processing_time_ms:.2f}ms)")

        print("="*60 + "\n")

    def export_events_to_json(self, filename: str) -> bool:
        """导出事件记录到JSON文件"""
        try:
            with self._lock:
                events_data = [asdict(event) for event in self._events]

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "statistics": self.get_statistics(),
                    "events": events_data
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"📁 表情调试数据已导出到: {filename}")
            return True
        except Exception as e:
            logger.error(f"❌ 导出调试数据失败: {e}")
            return False

    def clear_events(self):
        """清空事件记录"""
        with self._lock:
            self._events.clear()
            self._stats = {
                "total_events": 0,
                "successful_triggers": 0,
                "failed_triggers": 0,
                "emoji_to_emotion_mappings": 0,
                "processing_times": deque(maxlen=100),
                "error_counts": {},
                "source_types": {"emoji": 0, "emotion": 0, "text": 0}
            }
        logger.info("🗑️ 表情调试记录已清空")


# 全局调试器实例
emotion_debugger = EmotionDebugger()


def get_emotion_debugger() -> EmotionDebugger:
    """获取表情调试器实例"""
    return emotion_debugger


if __name__ == "__main__":
    # 测试调试器功能
    debugger = get_emotion_debugger()

    # 模拟一些事件
    debugger.log_emotion_received("😊", "emoji")
    debugger.log_emotion_mapped("😊", "happy", 2.5)
    debugger.log_emotion_triggered("happy", 15.3, True)

    debugger.log_emotion_received("sad", "emotion")
    debugger.log_emotion_triggered("sad", 12.1, True)

    debugger.log_emotion_error("unknown_emoji", "未识别的emoji", 1.2)

    # 打印调试报告
    debugger.print_debug_report()