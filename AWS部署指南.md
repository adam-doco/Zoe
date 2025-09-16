# Live2D小智AI系统 - AWS EC2部署指南

## 🎯 专用说明

你的EC2实例信息：
- **IP地址**: 47.129.128.20
- **实例类型**: t3.small (2 vCPU, 2GB RAM)
- **操作系统**: Ubuntu 22.04 LTS
- **地域**: Asia Pacific (Singapore)

---

## 🚀 快速部署

### 1. 部署前检查

**检查密钥文件:**
```bash
# 确保你的.pem密钥文件在项目目录中
ls -la *.pem

# 如果权限不对，修正权限
chmod 400 your-key-file.pem
```

**测试连接:**
```bash
# 替换为你的实际密钥文件名
ssh -i your-key-file.pem ubuntu@47.129.128.20

# 如果连接成功，输入 exit 退出
```

### 2. 一键部署

**使用AWS专用部署脚本:**
```bash
# 基本部署 (使用IP访问)
./aws-deploy.sh 47.129.128.20 your-key-file.pem

# 如果你有域名
./aws-deploy.sh 47.129.128.20 your-key-file.pem your-domain.com
```

**部署过程说明:**
```
1️⃣ 打包本地项目文件
2️⃣ 测试AWS连接
3️⃣ 上传项目到EC2
4️⃣ 自动配置系统环境
5️⃣ 部署验证
```

预计部署时间: **5-8分钟**

---

## 📋 部署后管理

### 连接到你的EC2

```bash
# SSH连接
ssh -i your-key-file.pem ubuntu@47.129.128.20

# 切换到应用用户
sudo su - xiaozhi
```

### 服务管理命令

**启动服务:**
```bash
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi /home/xiaozhi/start-xiaozhi.sh'
```

**停止服务:**
```bash
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi /home/xiaozhi/stop-xiaozhi.sh'
```

**查看状态:**
```bash
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi /home/xiaozhi/status-xiaozhi.sh'
```

**查看日志:**
```bash
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi tail -f /home/xiaozhi/xiaozhi-app/logs/*.log'
```

---

## 🌐 访问你的系统

### 直接访问

```
浏览器访问: http://47.129.128.20
```

**功能测试清单:**
- ✅ Live2D模型是否显示
- ✅ 聊天输入框是否可用
- ✅ 语音按钮是否工作
- ✅ 小智AI是否响应
- ✅ Live2D表情是否同步

### API接口测试

```bash
# 系统状态API
curl http://47.129.128.20/api/system_status

# Live2D控制API
curl -X POST http://47.129.128.20/api/live2d \
  -H "Content-Type: application/json" \
  -d '{"type":"action","name":"kaixin","source":"test"}'

# 聊天API
curl -X POST http://47.129.128.20/api/chat \
  -H "Content-Type: application/json" \
  -d '{"type":"user_message","text":"你好","sender":"user"}'
```

---

## 🔒 安全配置

### SSL证书配置 (HTTPS)

如果你有域名，可以配置免费SSL证书：

```bash
# 1. 连接到EC2
ssh -i your-key-file.pem ubuntu@47.129.128.20

# 2. 安装Certbot
sudo apt install certbot python3-certbot-nginx -y

# 3. 申请SSL证书 (替换为你的域名)
sudo certbot --nginx -d your-domain.com

# 4. 设置自动续期
sudo crontab -e
# 添加这行: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 增强安全设置

```bash
# 1. 修改SSH端口 (可选)
sudo vim /etc/ssh/sshd_config
# 修改 Port 22 为其他端口如 Port 2222
sudo systemctl restart sshd

# 2. 启用fail2ban防暴力破解
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

---

## 📊 性能监控

### 系统资源监控

```bash
# 查看系统负载
ssh -i your-key-file.pem ubuntu@47.129.128.20 'htop'

# 查看内存使用
ssh -i your-key-file.pem ubuntu@47.129.128.20 'free -h'

# 查看磁盘使用
ssh -i your-key-file.pem ubuntu@47.129.128.20 'df -h'

# 查看网络连接
ssh -i your-key-file.pem ubuntu@47.129.128.20 'netstat -tulpn'
```

### AWS CloudWatch监控

在AWS控制台可以查看：
- CPU使用率
- 网络流入/流出
- 磁盘读写
- 实例状态检查

---

## 💾 备份策略

### 创建AMI快照

```bash
# 在AWS控制台:
# 1. 选择你的EC2实例
# 2. 右键 → "Create Image"
# 3. 设置镜像名称: "xiaozhi-ai-backup-20241215"
# 4. 点击"Create Image"
```

### 手动数据备份

```bash
# 备份应用数据
ssh -i your-key-file.pem ubuntu@47.129.128.20 << 'EOF'
sudo -u xiaozhi bash -c '
cd ~
tar -czf xiaozhi-backup-$(date +%Y%m%d).tar.gz xiaozhi-app
echo "备份完成: xiaozhi-backup-$(date +%Y%m%d).tar.gz"
'
EOF

# 下载备份到本地
scp -i your-key-file.pem ubuntu@47.129.128.20:/home/xiaozhi/xiaozhi-backup-*.tar.gz ./
```

---

## 🚨 故障排除

### 常见问题

**1. 无法连接EC2实例**
```bash
# 检查安全组设置
# 确保SSH (22端口) 允许你的IP访问

# 检查实例状态
# AWS控制台确认实例为"running"状态

# 检查密钥文件权限
chmod 400 your-key-file.pem
```

**2. 网站无法访问**
```bash
# 检查服务状态
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi /home/xiaozhi/status-xiaozhi.sh'

# 重启服务
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi /home/xiaozhi/stop-xiaozhi.sh && sleep 3 && sudo -u xiaozhi /home/xiaozhi/start-xiaozhi.sh'

# 检查Nginx状态
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo systemctl status nginx'
```

**3. 小智AI无响应**
```bash
# 查看消息处理器日志
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi tail -100 /home/xiaozhi/xiaozhi-app/logs/handler.log'

# 检查网络连接到小智API
ssh -i your-key-file.pem ubuntu@47.129.128.20 'ping api.tenclass.net'

# 重启消息处理器
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi pkill -f simple_message_handler.py && sudo -u xiaozhi /home/xiaozhi/start-xiaozhi.sh'
```

### 紧急恢复

**如果系统完全异常:**
```bash
# 1. 停止所有服务
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo -u xiaozhi /home/xiaozhi/stop-xiaozhi.sh'

# 2. 清理进程和文件
ssh -i your-key-file.pem ubuntu@47.129.128.20 'sudo pkill -f python3; sudo rm -rf /tmp/xiaozhi_queues'

# 3. 重新部署
./aws-deploy.sh 47.129.128.20 your-key-file.pem
```

---

## 💰 成本控制

### EC2费用优化

**实例管理:**
```bash
# 临时停止实例 (停止计费，但EBS存储仍收费)
# AWS控制台: Instance State → Stop

# 重新启动实例 (IP地址可能变化)
# AWS控制台: Instance State → Start

# 完全终止实例 (彻底删除，停止所有费用)
# AWS控制台: Instance State → Terminate
```

**费用监控:**
- 启用AWS Billing Alerts
- 设置月费用预警 ($30-50)
- 定期查看Cost Explorer

### 弹性IP (可选)

如果需要固定IP地址：
```bash
# AWS控制台: EC2 → Elastic IPs → Allocate
# 然后Associate到你的实例
# 注意: 弹性IP有额外费用 (~$3.6/月)
```

---

## 📈 扩展建议

### 性能提升

**如果访问量增加:**
1. **升级实例**: t3.small → t3.medium
2. **增加EBS**: 20GB → 40GB
3. **配置CloudFront CDN**: 加速静态资源

**如果需要高可用:**
1. **多AZ部署**: 使用负载均衡器
2. **RDS数据库**: 替代本地存储
3. **Auto Scaling**: 自动扩缩容

### 域名配置

**如果你有域名:**
```bash
# 1. 在域名提供商处添加A记录
# 类型: A
# 名称: @ 或 xiaozhi
# 值: 47.129.128.20
# TTL: 300

# 2. 重新部署启用域名
./aws-deploy.sh 47.129.128.20 your-key-file.pem your-domain.com

# 3. 配置SSL证书
# (参考上面SSL配置部分)
```

---

## 🎯 成功验证清单

部署完成后，请验证以下项目：

**基础功能:**
- [ ] 可以访问 http://47.129.128.20
- [ ] Live2D模型正常显示
- [ ] 聊天输入框可以使用
- [ ] 小智AI响应正常
- [ ] Live2D表情会根据AI情感变化

**高级功能:**
- [ ] 语音识别功能正常 (需HTTPS)
- [ ] 语音识别后自动发送消息
- [ ] 多种情感表情都能正确显示
- [ ] API接口响应正常

**系统管理:**
- [ ] 可以SSH连接管理
- [ ] 服务启停脚本工作正常
- [ ] 日志记录正常
- [ ] 系统监控数据正常

---

## 🎉 总结

你的Live2D小智AI系统现在运行在：
- **🌐 访问地址**: http://47.129.128.20
- **💻 服务器**: AWS EC2 t3.small (新加坡)
- **💰 预估费用**: ~$25/月 (¥175)
- **🔧 管理方式**: SSH + 脚本管理

**下一步建议:**
1. 🌐 配置域名 (如果有的话)
2. 🔒 启用SSL证书 (HTTPS)
3. 📊 设置费用预警
4. 👥 邀请朋友测试使用

享受你的专属Live2D AI助手吧！🎭✨

---
第1步：清理端口占用

  # 杀死占用端口3000的所有进程
  sudo pkill -f server.py
  sudo pkill -f "python.*server"
  sudo lsof -ti:3000 | xargs sudo kill -9 2>/dev/null || true

  第2步：等待几秒让端口释放

  sleep 5

  第3步：重新启动服务

  sudo -u xiaozhi /home/xiaozhi/start-xiaozhi.sh

  第4步：检查状态

  sudo -u xiaozhi /home/xiaozhi/status-xiaozhi.sh

  如果还是有问题，试试重启整个系统：

  # 完全停止所有服务
  sudo -u xiaozhi /home/xiaozhi/stop-xiaozhi.sh
  sudo pkill -f python3
  sleep 5

  # 重新启动
  sudo -u xiaozhi /home/xiaozhi/start-xiaozhi.sh
  
*文档版本: AWS EC2 专用版*
*适用实例: 47.129.128.20*
*最后更新: 2024年9月*