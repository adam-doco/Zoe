#!/bin/bash
# Live2D小智AI系统 - AWS EC2专用部署脚本
# 适用于Ubuntu 22.04 LTS on AWS EC2
# 使用方法: chmod +x aws-deploy.sh && ./aws-deploy.sh [ec2_ip] [key_file] [domain]

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# 检查参数
if [ $# -lt 2 ]; then
    log_error "使用方法: $0 <ec2_ip> <key_file> [domain]"
    echo "例如: $0 47.129.128.20 xiaozhi-ai-key.pem"
    echo "或者: $0 47.129.128.20 xiaozhi-ai-key.pem xiaozhi.example.com"
    exit 1
fi

EC2_IP="$1"
KEY_FILE="$2"
DOMAIN="${3:-$EC2_IP}"
AWS_USER="ubuntu"  # AWS Ubuntu默认用户
APP_USER="xiaozhi" # 应用运行用户

# 检查密钥文件
if [ ! -f "$KEY_FILE" ]; then
    log_error "密钥文件不存在: $KEY_FILE"
    log_info "请确保.pem文件在当前目录，或提供完整路径"
    exit 1
fi

# 检查密钥文件权限
KEY_PERMS=$(stat -f %A "$KEY_FILE" 2>/dev/null || stat -c %a "$KEY_FILE" 2>/dev/null)
if [ "$KEY_PERMS" != "400" ]; then
    log_warn "修正密钥文件权限..."
    chmod 400 "$KEY_FILE"
fi

log_info "🚀 开始部署Live2D小智AI系统到AWS EC2"
log_info "📍 EC2实例: $EC2_IP"
log_info "🔑 密钥文件: $KEY_FILE"
log_info "🌐 访问域名: $DOMAIN"
log_info "👤 AWS用户: $AWS_USER"

# 检查本地项目文件
REQUIRED_FILES=("server.py" "simple_message_handler.py" "xiaozhi_device.json" "index.html")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        log_error "缺少必要文件: $file"
        exit 1
    fi
done

log_step "1️⃣ 打包项目文件..."
tar --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='*.md' \
    --exclude='deploy.sh' \
    --exclude='simple-deploy.sh' \
    --exclude='aws-deploy.sh' \
    --exclude='monitor.py' \
    --exclude='gunicorn.conf.py' \
    -czf xiaozhi-aws.tar.gz .

log_info "✅ 项目打包完成: xiaozhi-aws.tar.gz"

log_step "2️⃣ 测试AWS连接..."
if ! ssh -i "$KEY_FILE" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$AWS_USER@$EC2_IP" "echo 'AWS连接测试成功'"; then
    log_error "无法连接到AWS EC2实例"
    log_info "请检查："
    echo "  - EC2实例是否正在运行"
    echo "  - 安全组是否允许SSH (22端口)"
    echo "  - 密钥文件是否正确"
    exit 1
fi

log_step "3️⃣ 上传项目到EC2..."
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no xiaozhi-aws.tar.gz "$AWS_USER@$EC2_IP:/tmp/"
log_info "✅ 项目上传完成"

log_step "4️⃣ 在EC2上执行部署..."
ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "$AWS_USER@$EC2_IP" << EOF
    set -e

    echo "🔄 更新Ubuntu系统..."
    sudo apt update
    sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

    echo "📦 安装必要软件..."
    sudo apt install -y python3 python3-pip nginx ufw curl wget

    echo "👤 创建应用用户..."
    if ! id "$APP_USER" &>/dev/null; then
        sudo useradd -m -s /bin/bash $APP_USER
        sudo usermod -aG sudo $APP_USER
        echo "$APP_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/$APP_USER
    fi

    echo "🔥 配置UFW防火墙..."
    sudo ufw --force reset
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable

    echo "🏠 设置应用环境..."
    sudo -u $APP_USER bash << 'USEREOF'
        cd ~

        # 安装Python依赖
        python3 -m pip install --user --upgrade pip
        python3 -m pip install --user websockets aiohttp requests

        # 解压项目
        rm -rf xiaozhi-app
        mkdir xiaozhi-app
        cd xiaozhi-app
        tar -xzf /tmp/xiaozhi-aws.tar.gz

        # 创建目录和设置权限
        mkdir -p logs
        chmod +x server.py simple_message_handler.py
        chmod 600 xiaozhi_device.json

        # 修改server.py绑定所有地址
        sed -i 's/("127.0.0.1", port)/("0.0.0.0", port)/g' server.py

        echo "✅ 用户环境配置完成"
USEREOF

    echo "🌐 配置Nginx..."
    sudo tee /etc/nginx/sites-available/xiaozhi << 'NGXEOF'
server {
    listen 80;
    server_name $DOMAIN;

    # 安全头设置
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";

    # 静态资源优化
    location /Mould/ {
        alias /home/$APP_USER/xiaozhi-app/Mould/;
        expires 1h;
        add_header Cache-Control "public";

        # 启用gzip压缩
        gzip on;
        gzip_types application/json text/css application/javascript;
    }

    location /libs/ {
        alias /home/$APP_USER/xiaozhi-app/libs/;
        expires 1h;
        add_header Cache-Control "public";
        gzip on;
    }

    # API和主页面代理
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        # 超时设置
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # 请求大小限制
        client_max_body_size 10M;
    }

    # 日志设置
    access_log /var/log/nginx/xiaozhi_access.log;
    error_log /var/log/nginx/xiaozhi_error.log;
}
NGXEOF

    # 启用Nginx配置
    sudo ln -sf /etc/nginx/sites-available/xiaozhi /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t
    sudo systemctl restart nginx
    sudo systemctl enable nginx

    echo "🔧 创建服务管理脚本..."

    # 启动脚本
    sudo -u $APP_USER tee /home/$APP_USER/start-xiaozhi.sh << 'STARTEOF'
#!/bin/bash
cd /home/$APP_USER/xiaozhi-app

echo "🔍 检查服务状态..."
if pgrep -f "simple_message_handler.py" > /dev/null; then
    echo "⚠️ 消息处理器已在运行"
else
    echo "🔄 启动消息处理器..."
    nohup python3 simple_message_handler.py > logs/handler.log 2>&1 &
    echo \$! > handler.pid
    echo "✅ 消息处理器已启动 (PID: \$(cat handler.pid))"
fi

sleep 3

if pgrep -f "server.py" > /dev/null; then
    echo "⚠️ Web服务器已在运行"
else
    echo "🌐 启动Web服务器..."
    nohup python3 server.py > logs/server.log 2>&1 &
    echo \$! > server.pid
    echo "✅ Web服务器已启动 (PID: \$(cat server.pid))"
fi

echo ""
echo "📋 服务状态:"
ps aux | grep -E "(simple_message_handler|server\.py)" | grep -v grep || echo "⚠️ 未找到运行的服务"

echo ""
echo "🌐 访问地址: http://$DOMAIN"
echo "📊 查看日志: tail -f logs/*.log"
STARTEOF

    # 停止脚本
    sudo -u $APP_USER tee /home/$APP_USER/stop-xiaozhi.sh << 'STOPEOF'
#!/bin/bash
cd /home/$APP_USER/xiaozhi-app

echo "⏹️ 停止小智AI服务..."

# 停止消息处理器
if [ -f handler.pid ]; then
    if kill \$(cat handler.pid) 2>/dev/null; then
        echo "✅ 消息处理器已停止"
    else
        echo "⚠️ 消息处理器PID已失效，尝试强制停止..."
        pkill -f "simple_message_handler.py" || true
    fi
    rm -f handler.pid
fi

# 停止Web服务器
if [ -f server.pid ]; then
    if kill \$(cat server.pid) 2>/dev/null; then
        echo "✅ Web服务器已停止"
    else
        echo "⚠️ Web服务器PID已失效，尝试强制停止..."
        pkill -f "server.py" || true
    fi
    rm -f server.pid
fi

echo "✅ 所有服务已停止"
STOPEOF

    # 状态检查脚本
    sudo -u $APP_USER tee /home/$APP_USER/status-xiaozhi.sh << 'STATUSEOF'
#!/bin/bash
cd /home/$APP_USER/xiaozhi-app

echo "📊 Live2D小智AI系统状态报告"
echo "=============================="

# 检查进程状态
echo "🔍 进程状态:"
if pgrep -f "simple_message_handler.py" > /dev/null; then
    echo "  ✅ 消息处理器: 运行中 (PID: \$(pgrep -f simple_message_handler.py))"
else
    echo "  ❌ 消息处理器: 未运行"
fi

if pgrep -f "server.py" > /dev/null; then
    echo "  ✅ Web服务器: 运行中 (PID: \$(pgrep -f server.py))"
else
    echo "  ❌ Web服务器: 未运行"
fi

# 检查端口监听
echo ""
echo "🌐 端口状态:"
if netstat -tlnp 2>/dev/null | grep -q ":3000"; then
    echo "  ✅ 端口3000: 监听中"
else
    echo "  ❌ 端口3000: 未监听"
fi

if netstat -tlnp 2>/dev/null | grep -q ":80"; then
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
echo "  http://$DOMAIN"
echo "  http://$EC2_IP"

# 磁盘使用情况
echo ""
echo "💾 磁盘使用:"
df -h /home/$APP_USER/xiaozhi-app | tail -1 | awk '{print "  使用: " \$3 "/" \$2 " (" \$5 ")"}'

# 最近日志
echo ""
echo "📜 最近日志 (最后5行):"
if [ -f logs/server.log ]; then
    echo "  --- Web服务器日志 ---"
    tail -3 logs/server.log 2>/dev/null || echo "  无日志内容"
fi

if [ -f logs/handler.log ]; then
    echo "  --- 消息处理器日志 ---"
    tail -3 logs/handler.log 2>/dev/null || echo "  无日志内容"
fi
STATUSEOF

    # 设置脚本权限
    sudo chown $APP_USER:$APP_USER /home/$APP_USER/*.sh
    sudo chmod +x /home/$APP_USER/*.sh

    echo "🏃 启动服务..."
    sudo -u $APP_USER /home/$APP_USER/start-xiaozhi.sh

    sleep 8

    echo "🔍 最终检查..."
    sudo -u $APP_USER /home/$APP_USER/status-xiaozhi.sh

    echo ""
    echo "🧹 清理临时文件..."
    rm -f /tmp/xiaozhi-aws.tar.gz

EOF

log_step "5️⃣ 部署验证..."
sleep 3

# 测试HTTP服务
if curl -f -s "http://$EC2_IP/" > /dev/null; then
    log_info "✅ HTTP服务测试通过"
else
    log_warn "⚠️ HTTP服务可能需要更多时间启动"
fi

# 测试API服务
if curl -f -s "http://$EC2_IP/api/system_status" > /dev/null; then
    log_info "✅ API服务测试通过"
else
    log_warn "⚠️ API服务可能需要更多时间启动"
fi

# 清理本地文件
rm -f xiaozhi-aws.tar.gz

echo ""
log_info "🎉 AWS EC2部署完成！"
echo ""
echo "🌐 访问地址:"
echo "   http://$DOMAIN"
if [ "$DOMAIN" != "$EC2_IP" ]; then
    echo "   http://$EC2_IP"
fi
echo ""
echo "📋 管理命令:"
echo "   连接服务器: ssh -i $KEY_FILE $AWS_USER@$EC2_IP"
echo "   启动服务: ssh -i $KEY_FILE $AWS_USER@$EC2_IP 'sudo -u $APP_USER /home/$APP_USER/start-xiaozhi.sh'"
echo "   停止服务: ssh -i $KEY_FILE $AWS_USER@$EC2_IP 'sudo -u $APP_USER /home/$APP_USER/stop-xiaozhi.sh'"
echo "   查看状态: ssh -i $KEY_FILE $AWS_USER@$EC2_IP 'sudo -u $APP_USER /home/$APP_USER/status-xiaozhi.sh'"
echo "   查看日志: ssh -i $KEY_FILE $AWS_USER@$EC2_IP 'sudo -u $APP_USER tail -f /home/$APP_USER/xiaozhi-app/logs/*.log'"
echo ""
echo "🔒 SSL证书配置 (可选):"
echo "   如需HTTPS，可以配置Let's Encrypt:"
echo "   ssh -i $KEY_FILE $AWS_USER@$EC2_IP"
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d $DOMAIN"
echo ""
echo "🎯 下一步:"
echo "   1. 测试Live2D功能: 访问 http://$EC2_IP"
echo "   2. 测试语音识别功能"
echo "   3. 测试小智AI对话功能"
echo "   4. 如有域名，配置DNS解析到 $EC2_IP"