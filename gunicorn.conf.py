#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gunicorn配置文件 - 用于生产环境部署
使用方法: gunicorn -c gunicorn.conf.py server:app
"""

import multiprocessing
import os

# ===================
# 服务器套接字配置
# ===================

# 绑定地址和端口
bind = "127.0.0.1:3000"

# 监听队列大小 - 挂起连接的最大数量
backlog = 2048

# ===================
# Worker进程配置
# ===================

# Worker进程数量 - 根据CPU核心数自动计算
# 推荐公式: (2 x CPU核心数) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Worker类型
# sync: 同步工作进程 (默认)
# async: 异步工作进程 (适合I/O密集型应用)
worker_class = "sync"

# 每个Worker的线程数 (仅适用于gthread worker_class)
# threads = 2

# 每个Worker处理的最大并发连接数
worker_connections = 1000

# Worker进程超时时间(秒) - 超过此时间无响应的Worker将被重启
timeout = 60

# Keep-Alive超时时间(秒)
keepalive = 2

# ===================
# 应用配置
# ===================

# 预加载应用代码 - 提高性能，减少内存使用
preload_app = True

# Worker进程处理请求数上限 - 达到后重启Worker (防止内存泄漏)
max_requests = 1000

# 随机化重启范围 - 避免所有Worker同时重启
max_requests_jitter = 100

# ===================
# 服务器机制
# ===================

# 重用端口 (SO_REUSEPORT) - Linux 3.9+
# reuse_port = True

# 启用TCP_NODELAY
# tcp_nodelay = True

# ===================
# 日志配置
# ===================

# 访问日志文件路径
accesslog = "/home/xiaozhi/xiaozhi-app/logs/gunicorn_access.log"

# 错误日志文件路径
errorlog = "/home/xiaozhi/xiaozhi-app/logs/gunicorn_error.log"

# 日志级别
# debug, info, warning, error, critical
loglevel = "info"

# 访问日志格式
access_log_format = '''%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'''

# 日志格式说明:
# %(h)s - 远程地址
# %(l)s - 远程用户名
# %(u)s - 用户名
# %(t)s - 请求时间
# %(r)s - 状态行 (请求方法 URL HTTP版本)
# %(s)s - 状态码
# %(b)s - 响应字节数
# %(f)s - 引用页
# %(a)s - 用户代理
# %(D)s - 请求时间(微秒)

# 错误日志是否发送到syslog
# syslog = False

# ===================
# 进程命名
# ===================

# 进程名称前缀
proc_name = "xiaozhi-live2d-ai"

# ===================
# 用户和组设置
# ===================

# 运行用户 (生产环境建议使用非root用户)
user = "xiaozhi"
group = "xiaozhi"

# ===================
# 临时目录
# ===================

# 临时文件目录
tmp_upload_dir = "/tmp"

# ===================
# 安全设置
# ===================

# 限制HTTP首部大小
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# ===================
# 性能调优
# ===================

# 最大客户端连接数
max_requests_jitter = 50

# Paste配置文件路径 (可选)
# paste = None

# ===================
# SSL/TLS配置 (如果直接处理HTTPS)
# ===================

# SSL密钥文件
# keyfile = "/path/to/private.key"

# SSL证书文件
# certfile = "/path/to/certificate.crt"

# SSL CA证书文件
# ca_certs = "/path/to/ca_certificates.crt"

# SSL协议版本
# ssl_version = 3  # SSL.SSLv23

# SSL密码套件
# ciphers = "TLSv1"

# ===================
# 服务器钩子函数
# ===================

def on_starting(server):
    """服务器启动时执行"""
    server.log.info("🚀 Gunicorn服务器正在启动...")
    server.log.info(f"📊 配置信息:")
    server.log.info(f"   Workers: {workers}")
    server.log.info(f"   绑定地址: {bind}")
    server.log.info(f"   进程名: {proc_name}")

def on_reload(server):
    """重新加载时执行"""
    server.log.info("🔄 Gunicorn服务器重新加载配置")

def when_ready(server):
    """服务器准备就绪时执行"""
    server.log.info("✅ Gunicorn服务器已准备就绪，开始接受请求")

def on_exit(server):
    """服务器退出时执行"""
    server.log.info("⏹️ Gunicorn服务器正在关闭...")

def worker_int(worker):
    """Worker进程被中断时执行"""
    worker.log.info(f"⚠️ Worker进程 {worker.pid} 被中断")

def pre_fork(server, worker):
    """Fork Worker之前执行"""
    server.log.info(f"🔄 正在启动Worker进程 {worker.age}")

def post_fork(server, worker):
    """Fork Worker之后执行"""
    server.log.info(f"✅ Worker进程 {worker.pid} 启动成功")

def post_worker_init(worker):
    """Worker初始化完成后执行"""
    worker.log.info(f"🎯 Worker {worker.pid} 初始化完成，开始处理请求")

def worker_abort(worker):
    """Worker进程异常终止时执行"""
    worker.log.error(f"💥 Worker进程 {worker.pid} 异常终止")

# ===================
# 环境变量配置
# ===================

# 从环境变量获取配置 (优先级更高)
_bind = os.environ.get('GUNICORN_BIND')
if _bind:
    bind = _bind

_workers = os.environ.get('GUNICORN_WORKERS')
if _workers:
    workers = int(_workers)

_timeout = os.environ.get('GUNICORN_TIMEOUT')
if _timeout:
    timeout = int(_timeout)

_loglevel = os.environ.get('GUNICORN_LOG_LEVEL')
if _loglevel:
    loglevel = _loglevel.lower()

# ===================
# 开发环境配置覆盖
# ===================

# 检测是否为开发环境
if os.environ.get('FLASK_ENV') == 'development':
    # 开发环境使用单个Worker，便于调试
    workers = 1
    loglevel = "debug"
    reload = True  # 代码变化时自动重载
    timeout = 3600  # 开发时增加超时时间

    # 开发环境日志输出到控制台
    accesslog = "-"
    errorlog = "-"