#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表情系统测试
验证自动表情触发的完整流程
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.emotion_mapping import emotion_mapping, get_emotion_from_emoji, process_ai_emotion_data
from src.utils.emotion_debugger import get_emotion_debugger


def test_emoji_mapping():
    """测试emoji到表情的映射功能"""
    print("🧪 测试emoji映射功能")
    print("=" * 50)

    # 测试小智AI标准21种emoji
    test_emojis = [
        ("😶", "neutral"),
        ("🙂", "happy"),
        ("😆", "laughing"),
        ("😂", "funny"),
        ("😔", "sad"),
        ("😠", "angry"),
        ("😭", "crying"),
        ("😍", "loving"),
        ("😳", "embarrassed"),
        ("😲", "surprised"),
        ("😱", "shocked"),
        ("🤔", "thinking"),
        ("😉", "winking"),
        ("😎", "cool"),
        ("😌", "relaxed"),
        ("🤤", "delicious"),
        ("😘", "kissy"),
        ("😏", "confident"),
        ("😴", "sleepy"),
        ("😜", "silly"),
        ("🙄", "confused")
    ]

    success_count = 0
    for emoji, expected in test_emojis:
        result = get_emotion_from_emoji(emoji)
        if result == expected:
            print(f"✅ {emoji} → {result}")
            success_count += 1
        else:
            print(f"❌ {emoji} → {result} (期望: {expected})")

    print(f"\n📊 映射测试结果: {success_count}/{len(test_emojis)} 成功")
    return success_count == len(test_emojis)


def test_ai_data_processing():
    """测试AI数据处理功能"""
    print("\n🧪 测试AI数据处理功能")
    print("=" * 50)

    test_cases = [
        # 直接emoji数据
        ({"emoji": "😊"}, "happy"),
        ({"emoji": "😠"}, "angry"),

        # 直接emotion数据
        ({"emotion": "happy"}, "happy"),
        ({"emotion": "sad"}, "sad"),

        # 文本中包含emoji
        ({"text": "我很开心 😊 今天天气真好"}, "happy"),
        ({"text": "好生气啊 😠"}, "angry"),

        # 空数据
        ({}, "neutral"),
        ({"text": "没有emoji的普通文本"}, "neutral"),
    ]

    success_count = 0
    for data, expected in test_cases:
        result = process_ai_emotion_data(data)
        if result == expected:
            print(f"✅ {data} → {result}")
            success_count += 1
        else:
            print(f"❌ {data} → {result} (期望: {expected})")

    print(f"\n📊 AI数据处理测试结果: {success_count}/{len(test_cases)} 成功")
    return success_count == len(test_cases)


def test_emotion_debugger():
    """测试表情调试器功能"""
    print("\n🧪 测试表情调试器功能")
    print("=" * 50)

    debugger = get_emotion_debugger()
    debugger.clear_events()  # 清空之前的记录

    # 模拟一系列表情事件
    debugger.log_emotion_received("😊", "emoji")
    debugger.log_emotion_mapped("😊", "happy", 2.5)
    debugger.log_emotion_triggered("happy", 15.3, True)

    debugger.log_emotion_received("sad", "emotion")
    debugger.log_emotion_triggered("sad", 12.1, True)

    debugger.log_emotion_error("🤯", "未识别的emoji", 1.2)

    # 检查统计信息
    stats = debugger.get_statistics()
    expected_stats = {
        "total_events": 6,
        "successful_triggers": 2,
        "failed_triggers": 1,
    }

    success_count = 0
    for key, expected_value in expected_stats.items():
        actual_value = stats.get(key, 0)
        if actual_value == expected_value:
            print(f"✅ {key}: {actual_value}")
            success_count += 1
        else:
            print(f"❌ {key}: {actual_value} (期望: {expected_value})")

    debugger.print_debug_report()
    print(f"\n📊 调试器测试结果: {success_count}/{len(expected_stats)} 成功")
    return success_count == len(expected_stats)


def test_live2d_integration():
    """测试Live2D集成相关功能"""
    print("\n🧪 测试Live2D集成功能")
    print("=" * 50)

    # 测试所有表情是否都有对应的Live2D配置
    mapping = emotion_mapping
    validation_result = mapping.validate_mapping()

    print(f"📋 映射表验证结果:")
    print(f"   总情感数: {validation_result['total_emotions']}")
    print(f"   映射有效: {'✅' if validation_result['is_valid'] else '❌'}")

    if validation_result['invalid_actions']:
        print(f"   ❌ 无效动作: {validation_result['invalid_actions']}")

    if validation_result['invalid_expressions']:
        print(f"   ❌ 无效表情: {validation_result['invalid_expressions']}")

    # 打印类别覆盖情况
    print(f"\n📊 各类别情感覆盖:")
    for category, count in validation_result['coverage_by_category'].items():
        print(f"   {category}: {count} 个情感")

    return validation_result['is_valid']


async def test_async_processing():
    """测试异步处理功能"""
    print("\n🧪 测试异步处理功能")
    print("=" * 50)

    # 模拟并发表情处理
    async def process_emotion(emoji, delay=0.1):
        await asyncio.sleep(delay)
        result = get_emotion_from_emoji(emoji)
        print(f"⚡ 异步处理: {emoji} → {result}")
        return result

    # 并发处理多个emoji
    emojis = ["😊", "😠", "😭", "🤔", "😎"]
    tasks = [process_emotion(emoji, 0.05) for emoji in emojis]

    start_time = asyncio.get_event_loop().time()
    results = await asyncio.gather(*tasks)
    end_time = asyncio.get_event_loop().time()

    print(f"🚀 并发处理 {len(emojis)} 个emoji，耗时: {(end_time - start_time):.3f}s")
    print(f"📋 处理结果: {list(zip(emojis, results))}")

    return len(results) == len(emojis)


def main():
    """主测试函数"""
    print("🚀 Zoev3 表情系统完整测试")
    print("=" * 60)

    test_results = []

    # 运行所有测试
    test_results.append(("Emoji映射测试", test_emoji_mapping()))
    test_results.append(("AI数据处理测试", test_ai_data_processing()))
    test_results.append(("表情调试器测试", test_emotion_debugger()))
    test_results.append(("Live2D集成测试", test_live2d_integration()))

    # 异步测试
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        async_result = loop.run_until_complete(test_async_processing())
        test_results.append(("异步处理测试", async_result))
    finally:
        loop.close()

    # 汇总结果
    print("\n" + "=" * 60)
    print("📋 测试结果汇总")
    print("=" * 60)

    passed_tests = 0
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed_tests += 1

    total_tests = len(test_results)
    success_rate = passed_tests / total_tests * 100

    print(f"\n🎯 总体结果: {passed_tests}/{total_tests} 测试通过")
    print(f"📈 成功率: {success_rate:.1f}%")

    if passed_tests == total_tests:
        print("🎉 所有测试通过！表情系统运行良好")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)