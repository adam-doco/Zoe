#!/bin/bash
# Live2D小智AI系统 - 简化版云部署脚本
# 专为小型个人部署优化，最低配置服务器适用
# 使用方法: chmod +x simple-deploy.sh && ./simple-deploy.sh [server_ip] [domain]

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查参数
if [ $# -lt 1 ]; then
    log_error "使用方法: $0 <server_ip> [domain]"
    echo "例如: $0 192.168.1.100 或 $0 192.168.1.100 xiaozhi.com"
    exit 1
fi

SERVER_IP="$1"
DOMAIN="${2:-$SERVER_IP}"
USER="xiaozhi"

log_info "🚀 开始简化部署Live2D小智AI系统"
log_info "📍 服务器: $SERVER_IP"
log_info "🌐 访问地址: $DOMAIN"
log_info "💰 优化模式: 小型个人部署"

# 1. 打包项目 (排除不必要文件)
log_info "📦 打包项目文件..."
tar --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.md' \
    --exclude='云部署指南.md' \
    --exclude='部署指南.md' \
    --exclude='deploy.sh' \
    --exclude='monitor.py' \
    --exclude='gunicorn.conf.py' \
    -czf xiaozhi-simple.tar.gz .

log_info "✅ 项目打包完成"

# 2. 上传项目
log_info "📤 上传到服务器..."
scp xiaozhi-simple.tar.gz root@$SERVER_IP:/tmp/

# 3. 服务器部署
log_info "⚙️ 执行服务器配置..."
ssh root@$SERVER_IP << EOF
    set -e

    echo "📦 更新系统并安装基础软件..."
    apt update
    apt install -y python3 python3-pip nginx ufw

    echo "👤 创建用户..."
    if ! id "$USER" &>/dev/null; then
        useradd -m -s /bin/bash $USER
        echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER
    fi

    echo "🔥 配置防火墙..."
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80
    ufw --force enable

    echo "🏠 配置应用环境..."
    sudo -u $USER bash << 'USEREOF'
        cd ~

        # 安装Python依赖
        pip3 install websockets aiohttp requests --user

        # 解压项目
        rm -rf xiaozhi-app
        mkdir xiaozhi-app
        cd xiaozhi-app
        tar -xzf /tmp/xiaozhi-simple.tar.gz

        # 创建目录和设置权限
        mkdir -p logs
        chmod +x server.py simple_message_handler.py
        chmod 600 xiaozhi_device.json

        # 修改server.py绑定所有地址
        sed -i 's/("127.0.0.1", port)/("0.0.0.0", port)/g' server.py

        echo "✅ 应用环境配置完成"
USEREOF

    echo "🌐 配置Nginx..."
    cat > /etc/nginx/sites-available/xiaozhi << 'NGXEOF'
server {
    listen 80;
    server_name $DOMAIN;

    # 静态资源
    location /Mould/ {
        alias /home/$USER/xiaozhi-app/Mould/;
        expires 1h;
    }

    location /libs/ {
        alias /home/$USER/xiaozhi-app/libs/;
        expires 1h;
    }

    # 代理到Python应用
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        # 简化的超时设置
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # 基础安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
}
NGXEOF

    # 启用配置
    ln -sf /etc/nginx/sites-available/xiaozhi /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl restart nginx

    echo "🔧 创建启动脚本..."

    # 创建简单的启动脚本
    cat > /home/$USER/start-xiaozhi.sh << 'STARTEOF'
#!/bin/bash
cd /home/$USER/xiaozhi-app

echo "🔄 启动小智AI消息处理器..."
nohup python3 simple_message_handler.py > logs/handler.log 2>&1 &
echo \$! > handler.pid

sleep 3

echo "🌐 启动Web服务器..."
nohup python3 server.py > logs/server.log 2>&1 &
echo \$! > server.pid

echo "✅ 服务启动完成"
echo "📋 进程ID: 消息处理器=\$(cat handler.pid), Web服务=\$(cat server.pid)"
STARTEOF

    # 创建停止脚本
    cat > /home/$USER/stop-xiaozhi.sh << 'STOPEOF'
#!/bin/bash
cd /home/$USER/xiaozhi-app

echo "⏹️ 停止小智AI服务..."

if [ -f handler.pid ]; then
    kill \$(cat handler.pid) 2>/dev/null || true
    rm -f handler.pid
    echo "✅ 消息处理器已停止"
fi

if [ -f server.pid ]; then
    kill \$(cat server.pid) 2>/dev/null || true
    rm -f server.pid
    echo "✅ Web服务器已停止"
fi
STOPEOF

    # 设置脚本权限
    chown $USER:$USER /home/$USER/*.sh
    chmod +x /home/$USER/*.sh

    echo "🏃 启动服务..."
    sudo -u $USER /home/$USER/start-xiaozhi.sh

    sleep 5

    echo "📋 检查服务状态..."
    if pgrep -f "simple_message_handler.py" > /dev/null; then
        echo "✅ 消息处理器运行正常"
    else
        echo "❌ 消息处理器未运行"
    fi

    if pgrep -f "server.py" > /dev/null; then
        echo "✅ Web服务器运行正常"
    else
        echo "❌ Web服务器未运行"
    fi

    echo "🧹 清理临时文件..."
    rm -f /tmp/xiaozhi-simple.tar.gz

EOF

# 4. 部署验证
log_info "🔍 验证部署..."
sleep 5

if curl -f -s "http://$SERVER_IP/" > /dev/null; then
    log_info "✅ 部署成功！"
else
    log_warn "⚠️ 服务可能需要更多时间启动，请稍后验证"
fi

# 清理本地文件
rm -f xiaozhi-simple.tar.gz

echo ""
log_info "🎉 简化部署完成！"
echo ""
echo "🌐 访问地址: http://$DOMAIN"
echo ""
echo "📋 管理命令:"
echo "   启动服务: ssh $USER@$SERVER_IP './start-xiaozhi.sh'"
echo "   停止服务: ssh $USER@$SERVER_IP './stop-xiaozhi.sh'"
echo "   查看日志: ssh $USER@$SERVER_IP 'tail -f xiaozhi-app/logs/*.log'"
echo "   服务状态: ssh $USER@$SERVER_IP 'pgrep -f python3'"
echo ""
echo "💡 小贴士:"
echo "   - 服务器重启后需要手动启动: ./start-xiaozhi.sh"
echo "   - 日志文件位置: ~/xiaozhi-app/logs/"
echo "   - 如需SSL证书，可手动配置Let's Encrypt"