#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live2D小智AI系统监控脚本
功能：
- 系统资源监控 (CPU, 内存, 磁盘)
- 服务健康检查
- 日志分析
- 自动告警
- 性能统计

使用方法：
python3 monitor.py [--daemon] [--interval=60]
"""

import psutil
import requests
import time
import json
import logging
import argparse
import os
import sys
import signal
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

class XiaoZhiMonitor:
    """小智AI系统监控器"""

    def __init__(self, interval=60, log_dir="logs"):
        self.interval = interval
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.running = True

        # 配置日志
        self.setup_logging()

        # 监控指标阈值
        self.thresholds = {
            'cpu_percent': 80,
            'memory_percent': 80,
            'disk_percent': 85,
            'response_time': 5.0,  # 秒
            'error_rate': 0.1      # 10%
        }

        # 统计数据
        self.stats = {
            'start_time': time.time(),
            'check_count': 0,
            'error_count': 0,
            'alerts_sent': 0
        }

    def setup_logging(self):
        """设置日志配置"""
        self.logger = logging.getLogger('xiaozhi_monitor')
        self.logger.setLevel(logging.INFO)

        # 文件处理器
        file_handler = logging.FileHandler(self.log_dir / 'monitor.log')
        file_handler.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # 错误日志处理器
        error_handler = logging.FileHandler(self.log_dir / 'monitor_error.log')
        error_handler.setLevel(logging.ERROR)

        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(error_handler)

    def check_system_resources(self):
        """检查系统资源使用情况"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)

            # 内存使用情况
            memory = psutil.virtual_memory()

            # 磁盘使用情况
            disk = psutil.disk_usage('/')

            # 网络连接数
            net_connections = len(psutil.net_connections())

            # 进程数
            process_count = len(psutil.pids())

            resources = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3),
                'disk_percent': disk.percent,
                'disk_used_gb': disk.used / (1024**3),
                'disk_total_gb': disk.total / (1024**3),
                'net_connections': net_connections,
                'process_count': process_count,
                'timestamp': time.time()
            }

            self.logger.info(f"系统资源: CPU={cpu_percent:.1f}%, "
                           f"内存={memory.percent:.1f}% ({memory.used/1024**3:.1f}GB), "
                           f"磁盘={disk.percent:.1f}% ({disk.used/1024**3:.1f}GB)")

            # 检查阈值告警
            self.check_resource_alerts(resources)

            return resources

        except Exception as e:
            self.logger.error(f"系统资源检查失败: {e}")
            return None

    def check_service_health(self):
        """检查服务健康状态"""
        health_status = {
            'web_service': False,
            'api_service': False,
            'response_time': 0,
            'xiaozhi_connected': False,
            'error_message': None
        }

        try:
            # 检查Web服务
            start_time = time.time()
            response = requests.get('http://127.0.0.1:3000/', timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                health_status['web_service'] = True
                health_status['response_time'] = response_time
                self.logger.info(f"Web服务正常 (响应时间: {response_time:.2f}s)")
            else:
                self.logger.error(f"Web服务异常: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Web服务连接失败: {e}")
            health_status['error_message'] = str(e)

        try:
            # 检查API服务
            response = requests.get('http://127.0.0.1:3000/api/system_status', timeout=10)
            if response.status_code == 200:
                health_status['api_service'] = True
                data = response.json()

                # 检查小智AI连接状态
                if 'system_status' in data:
                    status_info = data['system_status']
                    health_status['xiaozhi_connected'] = status_info.get('websocket_connected', False)

                self.logger.info("API服务正常")
                if health_status['xiaozhi_connected']:
                    self.logger.info("小智AI连接正常")
                else:
                    self.logger.warning("小智AI连接异常")

            else:
                self.logger.error(f"API服务异常: HTTP {response.status_code}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"API服务连接失败: {e}")
            if not health_status['error_message']:
                health_status['error_message'] = str(e)

        return health_status

    def check_systemd_services(self):
        """检查systemd服务状态"""
        services = ['xiaozhi-handler', 'xiaozhi-app', 'nginx']
        service_status = {}

        for service in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service],
                    capture_output=True, text=True, timeout=10
                )
                is_active = result.stdout.strip() == 'active'
                service_status[service] = is_active

                if is_active:
                    self.logger.info(f"服务 {service} 正常运行")
                else:
                    self.logger.error(f"服务 {service} 未运行")

            except subprocess.TimeoutExpired:
                self.logger.error(f"检查服务 {service} 状态超时")
                service_status[service] = False
            except Exception as e:
                self.logger.error(f"检查服务 {service} 失败: {e}")
                service_status[service] = False

        return service_status

    def check_resource_alerts(self, resources):
        """检查资源告警"""
        alerts = []

        if resources['cpu_percent'] > self.thresholds['cpu_percent']:
            alerts.append(f"CPU使用率过高: {resources['cpu_percent']:.1f}%")

        if resources['memory_percent'] > self.thresholds['memory_percent']:
            alerts.append(f"内存使用率过高: {resources['memory_percent']:.1f}%")

        if resources['disk_percent'] > self.thresholds['disk_percent']:
            alerts.append(f"磁盘使用率过高: {resources['disk_percent']:.1f}%")

        for alert in alerts:
            self.logger.warning(f"⚠️ 资源告警: {alert}")
            self.stats['alerts_sent'] += 1

    def check_log_errors(self):
        """检查错误日志"""
        error_patterns = [
            'ERROR', 'Exception', 'Traceback',
            '500 Internal Server Error', 'Connection refused'
        ]

        log_files = [
            self.log_dir / 'handler.log',
            self.log_dir / 'handler_error.log',
            self.log_dir / 'app.log',
            self.log_dir / 'app_error.log'
        ]

        recent_errors = []
        cutoff_time = datetime.now() - timedelta(minutes=self.interval//60 + 1)

        for log_file in log_files:
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()

                    for line in lines[-100:]:  # 检查最近100行
                        for pattern in error_patterns:
                            if pattern.lower() in line.lower():
                                recent_errors.append(f"{log_file.name}: {line.strip()}")
                                break

                except Exception as e:
                    self.logger.error(f"读取日志文件 {log_file} 失败: {e}")

        if recent_errors:
            self.logger.warning(f"发现 {len(recent_errors)} 个最近错误")
            for error in recent_errors[-5:]:  # 只显示最新的5个错误
                self.logger.warning(f"🔍 {error}")

    def generate_report(self):
        """生成监控报告"""
        uptime = time.time() - self.stats['start_time']
        uptime_str = str(timedelta(seconds=int(uptime)))

        error_rate = (self.stats['error_count'] / max(self.stats['check_count'], 1)) * 100

        report = {
            'monitoring_uptime': uptime_str,
            'total_checks': self.stats['check_count'],
            'total_errors': self.stats['error_count'],
            'error_rate_percent': error_rate,
            'alerts_sent': self.stats['alerts_sent'],
            'last_check': datetime.now().isoformat()
        }

        # 保存报告到文件
        report_file = self.log_dir / 'monitor_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"📊 监控报告: 运行时间={uptime_str}, "
                        f"检查次数={self.stats['check_count']}, "
                        f"错误率={error_rate:.1f}%, "
                        f"告警次数={self.stats['alerts_sent']}")

        return report

    def run_check(self):
        """执行一次完整检查"""
        self.logger.info("🔍 开始系统检查...")
        self.stats['check_count'] += 1

        try:
            # 检查系统资源
            resources = self.check_system_resources()

            # 检查服务健康状态
            health = self.check_service_health()

            # 检查systemd服务
            services = self.check_systemd_services()

            # 检查错误日志
            self.check_log_errors()

            # 统计错误
            if not health['web_service'] or not health['api_service']:
                self.stats['error_count'] += 1

            # 每10次检查生成一次报告
            if self.stats['check_count'] % 10 == 0:
                self.generate_report()

            self.logger.info("✅ 系统检查完成")

        except Exception as e:
            self.logger.error(f"系统检查失败: {e}")
            self.stats['error_count'] += 1

    def signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"收到信号 {signum}，准备停止监控...")
        self.running = False

    def start_monitoring(self):
        """启动监控"""
        self.logger.info("🚀 启动Live2D小智AI系统监控")
        self.logger.info(f"📊 监控间隔: {self.interval}秒")
        self.logger.info(f"📁 日志目录: {self.log_dir.absolute()}")

        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            while self.running:
                self.run_check()

                # 等待下一次检查
                for i in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("用户中断，停止监控")
        except Exception as e:
            self.logger.error(f"监控异常: {e}")
        finally:
            # 生成最终报告
            final_report = self.generate_report()
            self.logger.info("📄 最终监控报告:")
            for key, value in final_report.items():
                self.logger.info(f"   {key}: {value}")

            self.logger.info("⏹️ 监控已停止")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Live2D小智AI系统监控')
    parser.add_argument('--interval', type=int, default=60,
                      help='监控间隔(秒), 默认60秒')
    parser.add_argument('--daemon', action='store_true',
                      help='以守护进程模式运行')
    parser.add_argument('--log-dir', default='logs',
                      help='日志目录，默认为logs')

    args = parser.parse_args()

    # 创建监控器
    monitor = XiaoZhiMonitor(interval=args.interval, log_dir=args.log_dir)

    if args.daemon:
        # 守护进程模式
        try:
            pid = os.fork()
            if pid > 0:
                print(f"监控进程启动，PID: {pid}")
                print(f"日志文件: {Path(args.log_dir).absolute() / 'monitor.log'}")
                print("使用 kill {pid} 停止监控")
                sys.exit(0)
        except OSError as e:
            print(f"fork失败: {e}")
            sys.exit(1)

        # 子进程
        os.chdir('/')
        os.setsid()
        os.umask(0)

        # 重定向标准输入输出
        sys.stdout.flush()
        sys.stderr.flush()

        si = open(os.devnull, 'r')
        so = open(os.devnull, 'a+')
        se = open(os.devnull, 'a+')

        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    # 启动监控
    monitor.start_monitoring()

if __name__ == "__main__":
    main()