#!/bin/bash
cd /home/xiaozhi/xiaozhi-app

echo "⏹️ 停止小智AI服务..."

# 停止消息处理器
if [ -f handler.pid ]; then
    if kill $(cat handler.pid) 2>/dev/null; then
        echo "✅ 消息处理器已停止"
    else
        echo "⚠️ 消息处理器PID已失效，尝试强制停止..."
        pkill -f "simple_message_handler.py" || true
    fi
    rm -f handler.pid
fi

# 停止Web服务器
if [ -f server.pid ]; then
    if kill $(cat server.pid) 2>/dev/null; then
        echo "✅ Web服务器已停止"
    else
        echo "⚠️ Web服务器PID已失效，尝试强制停止..."
        pkill -f "server.py" || true
    fi
    rm -f server.pid
fi

echo "✅ 所有服务已停止"