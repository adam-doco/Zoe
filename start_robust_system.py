#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动稳定的完整系统
使用增强的消息处理器，确保连接稳定性
"""

import subprocess
import time
import sys
import signal
import os

def start_server():
    """启动HTTP服务器"""
    print("🌐 启动HTTP服务器...")
    return subprocess.Popen([
        sys.executable, 'server.py'
    ], cwd='/Users/good/Desktop/Zoe')

def start_message_handler():
    """启动稳定消息处理器"""
    print("🤖 启动稳定消息处理器...")
    return subprocess.Popen([
        sys.executable, 'robust_message_handler.py'
    ], cwd='/Users/good/Desktop/Zoe')

def main():
    print("🚀 启动稳定的Live2D + 小智AI系统")
    print("=" * 50)
    
    processes = []
    
    try:
        # 启动HTTP服务器
        server_process = start_server()
        processes.append(('HTTP服务器', server_process))
        time.sleep(2)
        
        # 启动稳定消息处理器
        handler_process = start_message_handler()
        processes.append(('稳定消息处理器', handler_process))
        time.sleep(3)
        
        print("\n✅ 系统启动完成！")
        print("📍 前端地址: http://127.0.0.1:3000")
        print("🔗 连接状态: 监控心跳、自动重连")
        print("🛑 按 Ctrl+C 停止所有服务")
        print("=" * 50)
        
        # 等待所有进程
        for name, process in processes:
            try:
                process.wait()
            except KeyboardInterrupt:
                break
                
    except KeyboardInterrupt:
        print("\n⛔ 收到中断信号，正在停止服务...")
    
    finally:
        # 清理所有进程
        for name, process in processes:
            try:
                print(f"🔄 停止 {name}...")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"⚠️ 强制停止 {name}...")
                process.kill()
            except:
                pass
        
        print("👋 所有服务已停止")

if __name__ == "__main__":
    main()