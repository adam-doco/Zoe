#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live2D + 小智AI 完整系统启动脚本
一键启动完整的语音对话系统
"""

import asyncio
import signal
import sys
from live2d_xiaozhi_client import Live2DXiaozhiClient

# 全局客户端实例
client = None

def signal_handler(signum, frame):
    """处理Ctrl+C信号"""
    print("\n\n⛔ 收到中断信号，正在优雅关闭系统...")
    if client:
        try:
            # 尝试清理资源
            loop = asyncio.get_event_loop()
            loop.create_task(client.cleanup())
        except:
            pass
    print("👋 Live2D + 小智AI 系统已关闭，再见！")
    sys.exit(0)

async def main():
    """主运行函数"""
    global client
    
    print("🌟 Live2D + 小智AI 完整语音对话系统")
    print("=" * 60)
    print("🎭 Live2D虚拟形象 + 🤖 小智AI语音助手")
    print("💬 支持语音对话和文字聊天")
    print("❤️ 智能情感识别和Live2D动作同步")
    print("=" * 60)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    client = Live2DXiaozhiClient()
    
    try:
        # 第一步：初始化Live2D前端
        print("\n🎭 第一步：连接Live2D前端...")
        live2d_ready = await client.initialize_live2d()
        
        if not live2d_ready:
            print("❌ Live2D前端连接失败")
            print("💡 请确保前端正在运行:")
            print("   在另一个终端运行: python3 -m http.server 3000 --bind 127.0.0.1")
            print("   然后浏览器访问: http://localhost:3000")
            return False
        
        print("✅ Live2D前端连接成功")
        
        # 第二步：连接小智AI（走分支B）
        print("\n🤖 第二步：连接小智AI服务...")
        print("⏳ 正在建立连接...")
        
        # 启动连接（已激活设备应该走分支B）
        boot_task = asyncio.create_task(
            client.boot(force_new_device=False)
        )
        
        # 等待连接建立
        for i in range(30):
            await asyncio.sleep(1)
            state = client.get_current_state().value
            
            if state == "wsReady":
                print("✅ 小智AI连接成功")
                break
            elif state == "error":
                print("❌ 连接出现错误")
                return False
            
            if i % 5 == 0:  # 每5秒显示一次状态
                print(f"   连接状态: {state} ({i+1}/30)")
        else:
            print("⏰ 连接超时")
            print("💡 可能需要重新激活设备，请运行:")
            print("   python3 correct_activation_flow.py")
            return False
        
        # 第三步：系统就绪
        print("\n🎉 系统启动成功！")
        print("=" * 50)
        print("🎤 语音对话：直接说话即可")
        print("💬 文字聊天：浏览器页面右下角输入")
        print("🎭 Live2D控制：浏览器页面右侧按钮")
        print("🌐 前端地址：http://localhost:3000")
        print("=" * 50)
        
        # 发送欢迎消息
        print("\n🎬 发送欢迎消息...")
        await client.send_user_message("你好，Live2D系统已启动！")
        
        # 显示系统状态
        await asyncio.sleep(3)
        stats = client.get_live2d_stats()
        print(f"\n📊 系统状态:")
        print(f"   小智AI: {stats['xiaozhi_state']}")
        print(f"   WebSocket: connected")
        print(f"   会话ID: {client.websocket_client.session_id}")
        print(f"   音频: {client.websocket_client.downstream_sample_rate}Hz")
        
        # 进入运行循环
        print(f"\n🔄 系统运行中... (按 Ctrl+C 退出)")
        print(f"💡 现在可以开始语音对话了！")
        
        # 保持系统运行
        while True:
            await asyncio.sleep(1)
            
            # 每30秒显示一次活动状态
            if int(asyncio.get_event_loop().time()) % 30 == 0:
                current_stats = client.get_live2d_stats()
                print(f"💫 系统活动: 消息{current_stats['chat_messages']}条, TTS{current_stats['tts_events']}次")
        
    except Exception as e:
        print(f"\n❌ 系统启动异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if client:
            print("\n🧹 清理系统资源...")
            try:
                await client.cleanup()
            except:
                pass

if __name__ == "__main__":
    try:
        # 检查前置条件
        print("🔍 系统启动前检查...")
        print("1. 确保前端服务运行: python3 -m http.server 3000 --bind 127.0.0.1")
        print("2. 确保浏览器可以访问: http://localhost:3000")
        print("3. 确保网络连接正常")
        print("4. 确保设备已激活（如未激活请先运行激活流程）")
        
        input("\n按 Enter 键开始启动系统...")
        
        # 运行主系统
        success = asyncio.run(main())
        
        if not success:
            print("\n💡 启动失败解决方案:")
            print("1. 检查前端服务是否运行")
            print("2. 检查网络连接")
            print("3. 如需重新激活: python3 correct_activation_flow.py")
            print("4. 运行诊断工具: python3 connection_diagnosis.py")
        
    except KeyboardInterrupt:
        print("\n👋 系统启动被取消")
    except Exception as e:
        print(f"\n❌ 启动异常: {e}")