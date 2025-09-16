#!/bin/bash
cd /home/xiaozhi/xiaozhi-app

echo "📊 Live2D小智AI系统状态报告"
echo "=============================="

# 检查进程状态
echo "🔍 进程状态:"
if pgrep -f "simple_message_handler.py" > /dev/null; then
    echo "  ✅ 消息处理器: 运行中 (PID: $(pgrep -f simple_message_handler.py))"
else
    echo "  ❌ 消息处理器: 未运行"
fi

if pgrep -f "server.py" > /dev/null; then
    echo "  ✅ Web服务器: 运行中 (PID: $(pgrep -f server.py))"
else
    echo "  ❌ Web服务器: 未运行"
fi

# 检查端口监听
echo ""
echo "🌐 端口状态:"
if ss -tlnp 2>/dev/null | grep -q ":3000"; then
    echo "  ✅ 端口3000: 监听中"
else
    echo "  ❌ 端口3000: 未监听"
fi

if ss -tlnp 2>/dev/null | grep -q ":80"; then
    echo "  ✅ 端口80: 监听中 (Nginx)"
else
    echo "  ❌ 端口80: 未监听"
fi

# 检查服务健康
echo ""
echo "💗 服务健康检查:"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ | grep -q "200"; then
    echo "  ✅ Web服务: 健康"
else
    echo "  ❌ Web服务: 异常"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/system_status | grep -q "200"; then
    echo "  ✅ API服务: 健康"
else
    echo "  ❌ API服务: 异常"
fi

# 显示访问地址
echo ""
echo "🌐 访问地址:"
echo "  http://47.129.128.20"

# 磁盘使用情况
echo ""
echo "💾 磁盘使用:"
df -h /home/xiaozhi/xiaozhi-app | tail -1 | awk '{print "  使用: " $3 "/" $2 " (" $5 ")"}'

# 最近日志
echo ""
echo "📜 最近日志 (最后3行):"
if [ -f logs/server.log ]; then
    echo "  --- Web服务器日志 ---"
    tail -3 logs/server.log 2>/dev/null || echo "  无日志内容"
fi

if [ -f logs/handler.log ]; then
    echo "  --- 消息处理器日志 ---"
    tail -3 logs/handler.log 2>/dev/null || echo "  无日志内容"
fi