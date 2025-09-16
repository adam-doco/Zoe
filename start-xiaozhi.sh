#!/bin/bash
cd /home/xiaozhi/xiaozhi-app

echo "🔍 检查服务状态..."
if pgrep -f "simple_message_handler.py" > /dev/null; then
    echo "⚠️ 消息处理器已在运行"
else
    echo "🔄 启动消息处理器..."
    nohup python3 simple_message_handler.py > logs/handler.log 2>&1 &
    echo $! > handler.pid
    echo "✅ 消息处理器已启动 (PID: $(cat handler.pid))"
fi

sleep 3

if pgrep -f "server.py" > /dev/null; then
    echo "⚠️ Web服务器已在运行"
else
    echo "🌐 启动Web服务器..."
    nohup python3 server.py > logs/server.log 2>&1 &
    echo $! > server.pid
    echo "✅ Web服务器已启动 (PID: $(cat server.pid))"
fi

echo ""
echo "📋 服务状态:"
ps aux | grep -E "(simple_message_handler|server\.py)" | grep -v grep || echo "⚠️ 未找到运行的服务"

echo ""
echo "🌐 访问地址: http://47.129.128.20"
echo "📊 查看日志: tail -f logs/*.log"