#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持Live2D + 小智AI的HTTP服务器
支持POST请求和API调用
"""

import http.server
import socketserver
import json
import os
from urllib.parse import urlparse, parse_qs
import threading
import queue
import time

# 导入跨进程共享消息队列
from shared_queues import message_queue, ai_reply_queue, live2d_commands

# Live2D命令队列
live2d_command_queue = queue.Queue()

# 导入消息处理器以获取系统状态
try:
    from robust_message_handler import global_handler
except ImportError:
    # 如果robust版本不可用，回退到simple版本
    try:
        from simple_message_handler import global_handler
        print("⚠️ 使用simple_message_handler，建议使用robust版本")
    except ImportError:
        global_handler = None
        print("⚠️ 无法导入消息处理器，激活功能将不可用")

class Live2DHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """支持Live2D API的HTTP请求处理器"""
    
    def do_POST(self):
        """处理POST请求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/live2d':
            self.handle_live2d_api()
        elif parsed_path.path == '/execute-js':
            self.handle_execute_js()
        elif parsed_path.path == '/api/chat':
            self.handle_chat_api()
        elif parsed_path.path == '/api/activate':
            self.handle_activate_api()
        else:
            self.send_error(404, "API endpoint not found")
    
    def handle_live2d_api(self):
        """处理Live2D API调用"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 支持两种数据格式：
            # 1. 旧格式: {'action': ..., 'expression': ...}
            # 2. 新格式: {'type': ..., 'name': ..., 'source': ...}

            # 检查是否是新格式
            if 'type' in data and 'name' in data:
                # 新格式处理
                api_type = data.get('type')
                name = data.get('name')
                source = data.get('source', 'unknown')

                print(f"[API] 收到Live2D命令 (新格式): type={api_type}, name={name}, source={source}")

                # 将命令放入前端轮询队列（转换为前端期望的格式）
                self.queue_live2d_command(api_type, name)

                response_message = f"Live2D命令执行: {api_type}.{name}"
            else:
                # 旧格式处理（兼容性）
                action = data.get('action')
                expression = data.get('expression')

                print(f"[API] 收到Live2D命令 (旧格式): action={action}, expression={expression}")
                response_message = f"Live2D命令执行: {action}, {expression}"

            # 发送成功响应
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = {
                "status": "success",
                "message": response_message,
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            print(f"[API] Live2D API错误: {e}")
            self.send_error(500, str(e))

    def queue_live2d_command(self, api_type, name):
        """将Live2D命令放入前端轮询队列"""
        try:
            # 转换新格式到前端Live2DAPIServer期望的格式
            command = {
                'type': 'live2d_control',  # 前端Live2DAPIServer期望的类型
                'timestamp': time.time(),
                'source': 'emotion_controller'
            }

            # 根据类型设置对应字段
            if api_type == 'action':
                command['action'] = name
            elif api_type == 'expression':
                command['expression'] = name

            # 放入队列
            live2d_command_queue.put(command)
            print(f"[Live2D] 命令已加入队列: {command}")

        except Exception as e:
            print(f"[Live2D] 队列命令失败: {e}")
    
    def handle_execute_js(self):
        """处理JavaScript执行请求"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            js_code = data.get('code', '')
            print(f"[API] 收到JS执行请求: {js_code[:50]}...")
            
            # 发送成功响应
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "status": "success",
                "message": "JavaScript executed",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            print(f"[API] JS执行错误: {e}")
            self.send_error(500, str(e))
    
    def handle_chat_api(self):
        """处理聊天API"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            message_type = data.get('type')
            text = data.get('text', '')
            sender = data.get('sender', 'user')
            
            print(f"[CHAT] 收到消息: {sender} - {text}")
            
            # 将消息放入队列供Live2D客户端处理
            if message_type == 'user_message':
                message_queue.put({
                    'type': 'user_message',
                    'text': text,
                    'sender': sender,
                    'timestamp': time.time(),
                    'request_id': f"msg_{int(time.time() * 1000)}"
                })
                print(f"[CHAT] 消息已放入队列: {text}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "status": "success",
                "message": "Message received and queued for processing",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            print(f"[CHAT] 聊天API错误: {e}")
            self.send_error(500, str(e))
    
    def do_GET(self):
        """处理GET请求，包括AI回复的轮询"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/poll_reply':
            self.handle_poll_reply()
        elif parsed_path.path == '/api/poll_live2d':
            self.handle_poll_live2d()
        elif parsed_path.path == '/api/system_status':
            self.handle_system_status()
        else:
            # 处理静态文件
            super().do_GET()
    
    def handle_poll_reply(self):
        """处理前端轮询AI回复"""
        try:
            # 收集所有可用的AI回复
            replies = []
            max_replies = 10  # 限制一次最多获取10条回复，防止无限循环

            for _ in range(max_replies):
                if not ai_reply_queue.empty():
                    try:
                        reply = ai_reply_queue.get_nowait()
                        replies.append(reply)
                        print(f"[POLL] 获取AI回复: {reply.get('text', '')[:50]}...")
                    except:
                        break  # 队列为空时跳出
                else:
                    break

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if replies:
                response = {
                    "status": "success",
                    "has_reply": True,
                    "replies": replies,  # 返回所有回复
                    "count": len(replies),
                    "timestamp": time.time()
                }
                print(f"[POLL] 发送{len(replies)}条AI回复到前端")
            else:
                # 没有回复
                response = {
                    "status": "success",
                    "has_reply": False,
                    "timestamp": time.time()
                }

            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"[POLL] 轮询回复错误: {e}")
            self.send_error(500, str(e))

    def handle_poll_live2d(self):
        """处理前端轮询Live2D命令"""
        try:
            # 检查是否有Live2D命令
            if not live2d_command_queue.empty():
                command = live2d_command_queue.get()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                response = {
                    "status": "success",
                    "has_command": True,
                    "command": command,
                    "timestamp": time.time()
                }

                print(f"[Live2D Poll] 发送Live2D命令到前端: {command}")
            else:
                # 没有命令
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                response = {
                    "status": "success",
                    "has_command": False,
                    "timestamp": time.time()
                }

            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"[Live2D Poll] 轮询Live2D命令错误: {e}")
            self.send_error(500, str(e))
    
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def handle_activate_api(self):
        """处理激活重连API"""
        try:
            # 使用文件信号机制来触发激活
            activation_signal_file = "/tmp/xiaozhi_activation_request"

            # 创建激活信号文件
            with open(activation_signal_file, 'w') as f:
                f.write(f"activation_request:{time.time()}")

            print(f"[ACTIVATE] 创建激活信号文件: {activation_signal_file}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = {
                "status": "success",
                "message": "激活请求已发送",
                "timestamp": time.time()
            }

            self.wfile.write(json.dumps(response).encode('utf-8'))
            print(f"[ACTIVATE] 激活请求已通过信号文件发送")

        except Exception as e:
            print(f"[ACTIVATE] 激活API错误: {e}")
            self.send_error(500, str(e))

    def handle_system_status(self):
        """处理系统状态查询"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if global_handler is None:
                response = {
                    "status": "error",
                    "message": "Message handler not available",
                    "is_standby": True,
                    "timestamp": time.time()
                }
            else:
                status_info = global_handler.get_system_status()
                response = {
                    "status": "success",
                    "system_status": status_info,
                    "timestamp": time.time()
                }

            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"[STATUS] 系统状态API错误: {e}")
            self.send_error(500, str(e))

    def end_headers(self):
        """添加CORS头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def start_server(port=3000, directory=None):
    """启动HTTP服务器"""
    if directory:
        os.chdir(directory)
    
    handler = Live2DHTTPRequestHandler
    
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"🌐 Live2D服务器启动成功")
        print(f"📍 地址: http://127.0.0.1:{port}")
        print(f"📁 目录: {os.getcwd()}")
        print(f"✅ 支持POST API调用")
        print("=" * 50)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⛔ 服务器关闭")

if __name__ == "__main__":
    import sys
    
    port = 3000
    directory = "/Users/good/Desktop/Zoe"
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    if len(sys.argv) > 2:
        directory = sys.argv[2]
    
    start_server(port, directory)