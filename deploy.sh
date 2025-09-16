#!/bin/bash
# Live2D小智AI系统云部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh [server_ip] [domain]
# 例如: ./deploy.sh 192.168.1.100 xiaozhi.example.com

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 输出函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查参数
if [ $# -lt 1 ]; then
    log_error "使用方法: $0 <server_ip> [domain]"
    echo "例如: $0 192.168.1.100 xiaozhi.example.com"
    exit 1
fi

SERVER_IP="$1"
DOMAIN="${2:-$SERVER_IP}"
USER="xiaozhi"
APP_DIR="/home/$USER/xiaozhi-app"

log_info "开始部署Live2D小智AI系统到云服务器"
log_info "服务器IP: $SERVER_IP"
log_info "域名: $DOMAIN"

# 检查本地依赖
if ! command -v ssh &> /dev/null; then
    log_error "SSH客户端未安装，请先安装"
    exit 1
fi

if ! command -v scp &> /dev/null; then
    log_error "SCP客户端未安装，请先安装"
    exit 1
fi

# 检查项目文件
REQUIRED_FILES=("server.py" "simple_message_handler.py" "xiaozhi_device.json" "index.html")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        log_error "缺少必要文件: $file"
        exit 1
    fi
done

log_info "✅ 本地环境检查完成"

# 1. 打包项目文件
log_info "🏗️ 打包项目文件..."
tar --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='/tmp/xiaozhi_queues' \
    --exclude='*.log' \
    --exclude='云部署指南.md' \
    --exclude='部署指南.md' \
    -czf xiaozhi-project.tar.gz .

log_info "✅ 项目打包完成: xiaozhi-project.tar.gz"

# 2. 上传到服务器
log_info "📤 上传项目到服务器..."
scp xiaozhi-project.tar.gz root@$SERVER_IP:/tmp/
log_info "✅ 项目上传完成"

# 3. 连接到服务器执行部署
log_info "🚀 在服务器上执行部署..."
ssh root@$SERVER_IP << EOF
    set -e

    echo "🔄 更新系统包..."
    apt update && apt upgrade -y

    echo "📦 安装基础软件..."
    apt install -y curl wget git vim htop net-tools python3 python3-pip python3-venv
    apt install -y nginx supervisor ufw fail2ban

    echo "👤 创建应用用户..."
    if ! id "$USER" &>/dev/null; then
        useradd -m -s /bin/bash $USER
        usermod -aG sudo $USER
        echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER
    fi

    echo "🔥 配置防火墙..."
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 'Nginx Full'
    ufw --force enable

    echo "🏠 切换到应用用户并设置环境..."
    sudo -u $USER bash << 'USEREOF'
        cd ~

        # 创建Python虚拟环境
        python3 -m venv ~/xiaozhi-env
        source ~/xiaozhi-env/bin/activate

        # 安装Python依赖
        pip install --upgrade pip
        pip install websockets aiohttp requests gunicorn psutil

        # 解压项目
        if [ -d "xiaozhi-app" ]; then
            rm -rf xiaozhi-app
        fi
        mkdir xiaozhi-app
        cd xiaozhi-app
        tar -xzf /tmp/xiaozhi-project.tar.gz

        # 创建必要目录
        mkdir -p logs
        mkdir -p /tmp/xiaozhi-queues

        # 设置文件权限
        chmod +x server.py simple_message_handler.py
        chmod 600 xiaozhi_device.json

        echo "✅ 用户环境设置完成"
USEREOF

    # 修改server.py为生产配置
    echo "⚙️ 修改应用配置..."
    sudo -u $USER bash << 'USEREOF'
        cd ~/xiaozhi-app

        # 创建生产版本的server.py配置
        sed -i 's/("127.0.0.1", port)/("0.0.0.0", port)/g' server.py
        sed -i 's|directory = "/Users/good/Desktop/Zoe"|directory = "/home/$USER/xiaozhi-app"|g' server.py
USEREOF

    echo "🔧 创建系统服务..."

    # 消息处理器服务
    cat > /etc/systemd/system/xiaozhi-handler.service << 'SVCEOF'
[Unit]
Description=XiaoZhi AI Message Handler
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/xiaozhi-app
Environment=PATH=/home/$USER/xiaozhi-env/bin
ExecStart=/home/$USER/xiaozhi-env/bin/python simple_message_handler.py
Restart=always
RestartSec=10
StandardOutput=file:/home/$USER/xiaozhi-app/logs/handler.log
StandardError=file:/home/$USER/xiaozhi-app/logs/handler_error.log

[Install]
WantedBy=multi-user.target
SVCEOF

    # Flask应用服务
    cat > /etc/systemd/system/xiaozhi-app.service << 'SVCEOF'
[Unit]
Description=XiaoZhi AI Flask Application
After=network.target xiaozhi-handler.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/xiaozhi-app
Environment=PATH=/home/$USER/xiaozhi-env/bin
ExecStart=/home/$USER/xiaozhi-env/bin/gunicorn --bind 127.0.0.1:3000 --workers 4 --timeout 60 server:app
Restart=always
RestartSec=10
StandardOutput=file:/home/$USER/xiaozhi-app/logs/app.log
StandardError=file:/home/$USER/xiaozhi-app/logs/app_error.log

[Install]
WantedBy=multi-user.target
SVCEOF

    echo "🌐 配置Nginx..."

    # Nginx配置
    cat > /etc/nginx/sites-available/xiaozhi << 'NGXEOF'
server {
    listen 80;
    server_name $DOMAIN;

    # 静态文件处理
    location /Mould/ {
        alias /home/$USER/xiaozhi-app/Mould/;
        expires 1d;
        add_header Cache-Control "public, immutable";
        gzip on;
        gzip_types application/json;
    }

    location /libs/ {
        alias /home/$USER/xiaozhi-app/libs/;
        expires 1d;
        add_header Cache-Control "public, immutable";
        gzip on;
    }

    # API接口代理
    location /api/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 主页面
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
    }

    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # 日志
    access_log /var/log/nginx/xiaozhi_access.log;
    error_log /var/log/nginx/xiaozhi_error.log;

    # 限制请求大小
    client_max_body_size 10M;
}
NGXEOF

    # 启用Nginx配置
    ln -sf /etc/nginx/sites-available/xiaozhi /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t

    echo "🏃 启动服务..."
    systemctl daemon-reload

    # 启动服务
    systemctl enable xiaozhi-handler
    systemctl enable xiaozhi-app
    systemctl enable nginx

    systemctl start xiaozhi-handler
    sleep 5
    systemctl start xiaozhi-app
    systemctl reload nginx

    echo "📋 服务状态检查..."
    systemctl status xiaozhi-handler --no-pager || true
    systemctl status xiaozhi-app --no-pager || true
    systemctl status nginx --no-pager || true

    echo "🧹 清理临时文件..."
    rm -f /tmp/xiaozhi-project.tar.gz

EOF

# 4. 验证部署
log_info "🔍 验证部署状态..."

# 等待服务启动
sleep 10

# 检查HTTP服务
if curl -f -s "http://$SERVER_IP/" > /dev/null; then
    log_info "✅ HTTP服务正常"
else
    log_warn "⚠️ HTTP服务可能有问题，请检查服务状态"
fi

# 检查API服务
if curl -f -s "http://$SERVER_IP/api/system_status" > /dev/null; then
    log_info "✅ API服务正常"
else
    log_warn "⚠️ API服务可能有问题，请检查服务状态"
fi

# 清理本地临时文件
rm -f xiaozhi-project.tar.gz

log_info "🎉 部署完成！"
echo ""
echo "🌐 访问地址:"
echo "   HTTP: http://$DOMAIN"
if [ "$DOMAIN" != "$SERVER_IP" ]; then
    echo "   IP直访: http://$SERVER_IP"
fi
echo ""
echo "📋 管理命令:"
echo "   查看服务状态: ssh root@$SERVER_IP 'systemctl status xiaozhi-handler xiaozhi-app nginx'"
echo "   查看日志: ssh $USER@$SERVER_IP 'tail -f ~/xiaozhi-app/logs/*.log'"
echo "   重启服务: ssh root@$SERVER_IP 'systemctl restart xiaozhi-handler xiaozhi-app'"
echo ""
echo "🔒 安全建议:"
echo "   1. 配置SSL证书 (推荐Let's Encrypt)"
echo "   2. 修改SSH默认端口"
echo "   3. 设置密钥登录，禁用密码登录"
echo "   4. 定期更新系统和依赖包"
echo ""
echo "📖 详细文档: 云部署指南.md"