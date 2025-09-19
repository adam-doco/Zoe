#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
聊天对话显示组件 - 使用WebView实现现代化聊天界面
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl

logger = logging.getLogger(__name__)


class ChatBridge(QObject):
    """Python与JavaScript通信桥接类"""

    # 信号定义
    messageAdded = pyqtSignal(str, str)  # 消息内容, 发送者类型

    def __init__(self):
        super().__init__()
        self._message_count = 0

    @pyqtSlot(str, str)
    def addMessage(self, text, sender):
        """从JavaScript调用：添加消息"""
        self._message_count += 1
        self.messageAdded.emit(text, sender)
        logger.debug(f"通过JS桥接添加{sender}消息: {text[:50]}...")

    @pyqtSlot()
    def getMessageCount(self):
        """获取消息数量"""
        return self._message_count


class ChatWidget(QWidget):
    """
    基于WebView的现代化聊天组件
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # 创建WebView和通信桥接
        self._web_view = None
        self._bridge = None
        self._channel = None
        self._message_count = 0

        self._init_ui()
        self._setup_web_interface()

        self.logger.info("WebView聊天组件初始化完成")

    def _init_ui(self):
        """初始化UI布局"""
        # 设置基础样式
        self.setStyleSheet("""
            ChatWidget {
                background-color: transparent;
            }
        """)

        # 创建布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建WebView
        self._web_view = QWebEngineView()
        self._web_view.setStyleSheet("""
            QWebEngineView {
                background: transparent;
                background-color: rgba(0, 0, 0, 0);
            }
        """)

        layout.addWidget(self._web_view)
        self.setLayout(layout)

    def _setup_web_interface(self):
        """设置Web界面和JavaScript通信"""
        try:
            # 设置WebEngine页面背景为透明
            from PyQt5.QtWebEngineWidgets import QWebEnginePage
            from PyQt5.QtCore import Qt

            # 创建自定义页面并设置透明背景
            page = self._web_view.page()
            page.setBackgroundColor(Qt.transparent)

            # 创建通信桥接
            self._bridge = ChatBridge()
            self._bridge.messageAdded.connect(self._on_message_added)

            # 创建Web通道
            self._channel = QWebChannel()
            self._channel.registerObject('chatBridge', self._bridge)
            page.setWebChannel(self._channel)

            # 加载HTML文件
            html_file = Path(__file__).parent / "chat_interface.html"
            if html_file.exists():
                self._web_view.load(QUrl.fromLocalFile(str(html_file.absolute())))
                self.logger.info(f"加载聊天界面: {html_file}")
            else:
                self.logger.error(f"聊天界面文件不存在: {html_file}")
                self._load_fallback_html()

        except Exception as e:
            self.logger.error(f"设置Web界面失败: {e}", exc_info=True)
            self._load_fallback_html()

    def _load_fallback_html(self):
        """加载后备HTML内容"""
        fallback_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: system-ui;
                    background: transparent;
                    margin: 10px;
                    color: #333;
                }
                .error {
                    color: #ff4444;
                    text-align: center;
                    padding: 20px;
                }
            </style>
        </head>
        <body>
            <div class="error">
                <p>聊天界面加载失败</p>
                <p>请检查chat_interface.html文件</p>
            </div>
        </body>
        </html>
        """
        self._web_view.setHtml(fallback_html)

    def _on_message_added(self, text, sender):
        """处理消息添加信号"""
        self._message_count += 1
        self.logger.debug(f"消息计数更新: {self._message_count}")

    def add_user_message(self, message: str):
        """添加用户消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._add_message_to_web("user", "您", message, timestamp)

    def add_ai_message(self, message: str):
        """添加AI回复消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._add_message_to_web("ai", "Zoe", message, timestamp)

    def add_system_message(self, message: str):
        """添加系统消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._add_message_to_web("system", "系统", message, timestamp)

    def _add_message_to_web(self, msg_type: str, sender: str, content: str, timestamp: str):
        """将消息添加到Web界面"""
        try:
            # 转义JavaScript中的特殊字符
            content_escaped = content.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')

            # 调用JavaScript函数添加消息，使用安全的方式检查API是否存在
            js_code = f"""
                if (window.chatAPI && window.chatAPI.addMessage) {{
                    window.chatAPI.addMessage('{content_escaped}', '{msg_type}');
                }} else {{
                    console.error('chatAPI not ready, message:', '{content_escaped}');
                    setTimeout(function() {{
                        if (window.chatAPI && window.chatAPI.addMessage) {{
                            window.chatAPI.addMessage('{content_escaped}', '{msg_type}');
                        }}
                    }}, 100);
                }}
            """
            self._web_view.page().runJavaScript(js_code)

            self._message_count += 1
            self.logger.debug(f"添加{msg_type}消息到Web界面: {content[:50]}...")

        except Exception as e:
            self.logger.error(f"添加消息到Web界面失败: {e}", exc_info=True)

    def clear_messages(self):
        """清空所有消息"""
        try:
            js_code = "window.chatAPI.clearMessages();"
            self._web_view.page().runJavaScript(js_code)
            self._message_count = 0
            self.logger.info("清空聊天记录")
        except Exception as e:
            self.logger.error(f"清空消息失败: {e}", exc_info=True)

    def show_typing_indicator(self):
        """显示正在输入指示器"""
        try:
            js_code = "window.chatAPI.showTypingIndicator();"
            self._web_view.page().runJavaScript(js_code)
        except Exception as e:
            self.logger.error(f"显示输入指示器失败: {e}", exc_info=True)

    def hide_typing_indicator(self):
        """隐藏正在输入指示器"""
        try:
            js_code = "window.chatAPI.hideTypingIndicator();"
            self._web_view.page().runJavaScript(js_code)
        except Exception as e:
            self.logger.error(f"隐藏输入指示器失败: {e}", exc_info=True)

    def get_message_count(self):
        """获取消息数量"""
        return self._message_count

    def scroll_to_bottom(self):
        """滚动到底部"""
        try:
            js_code = "window.chatAPI.scrollToBottom();"
            self._web_view.page().runJavaScript(js_code)
        except Exception as e:
            self.logger.error(f"滚动到底部失败: {e}", exc_info=True)


if __name__ == "__main__":
    """测试聊天组件"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 创建测试窗口
    widget = ChatWidget()
    widget.setWindowTitle("Zoe Chat Widget Test")
    widget.resize(400, 600)
    widget.show()

    # 添加测试消息
    widget.add_system_message("聊天组件测试开始")
    widget.add_user_message("你好，这是用户消息测试")
    widget.add_ai_message("你好！这是AI回复消息，测试圆角气泡效果")
    widget.add_ai_message("支持多条AI消息，每条都是独立的气泡")
    widget.add_user_message("很好！现在界面看起来现代化多了")

    sys.exit(app.exec_())