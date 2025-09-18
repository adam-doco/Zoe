# -*- coding: utf-8 -*-
"""
聊天对话显示组件 - 适配Zoev3项目
"""

import html
from datetime import datetime
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QScrollBar,
    QHBoxLayout, QPushButton, QLabel
)

import logging
logger = logging.getLogger(__name__)


class ChatWidget(QWidget):
    """
    聊天对话显示组件 - Zoev3专用版本
    支持显示用户消息、AI回复和系统消息
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_styles()

        # 消息计数
        self._message_count = 0
        # 是否自动滚动
        self._auto_scroll = True

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 顶部工具栏
        toolbar_layout = QHBoxLayout()

        # 消息计数标签
        self._message_count_label = QLabel("聊天记录: 0条")
        self._message_count_label.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        toolbar_layout.addWidget(self._message_count_label)

        toolbar_layout.addStretch()

        # 自动滚动开关
        self._auto_scroll_button = QPushButton("自动滚动: 开")
        self._auto_scroll_button.setMaximumWidth(80)
        self._auto_scroll_button.setCheckable(True)
        self._auto_scroll_button.setChecked(True)
        self._auto_scroll_button.clicked.connect(self._toggle_auto_scroll)
        toolbar_layout.addWidget(self._auto_scroll_button)

        # 清空按钮
        self._clear_button = QPushButton("清空")
        self._clear_button.setMaximumWidth(50)
        self._clear_button.clicked.connect(self.clear_history)
        toolbar_layout.addWidget(self._clear_button)

        # 滚动到底部按钮
        self._scroll_bottom_button = QPushButton("↓")
        self._scroll_bottom_button.setMaximumWidth(25)
        self._scroll_bottom_button.clicked.connect(self._scroll_to_bottom)
        toolbar_layout.addWidget(self._scroll_bottom_button)

        layout.addLayout(toolbar_layout)

        # 聊天显示区域
        self._chat_browser = QTextBrowser(self)
        self._chat_browser.setReadOnly(True)
        self._chat_browser.setOpenExternalLinks(False)
        self._chat_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._chat_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 设置字体
        font = QFont("Microsoft YaHei", 10)
        self._chat_browser.setFont(font)

        layout.addWidget(self._chat_browser)

    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            ChatWidget {
                background-color: transparent;
            }
            QTextBrowser {
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                background-color: rgba(240, 240, 240, 0.9);
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(230, 230, 230, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(220, 220, 220, 0.9);
            }
            QPushButton:checked {
                background-color: rgba(0, 122, 255, 0.2);
                color: #007AFF;
            }
        """)

    def _toggle_auto_scroll(self):
        """切换自动滚动"""
        self._auto_scroll = self._auto_scroll_button.isChecked()
        if self._auto_scroll:
            self._auto_scroll_button.setText("自动滚动: 开")
            self._scroll_to_bottom()
        else:
            self._auto_scroll_button.setText("自动滚动: 关")

    def add_user_message(self, message: str):
        """添加用户消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._add_message("user", "您", message, timestamp)

    def add_ai_message(self, message: str):
        """添加AI回复消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._add_message("ai", "小智", message, timestamp)

    def add_system_message(self, message: str):
        """添加系统消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._add_message("system", "系统", message, timestamp)

    def _add_message(self, msg_type: str, sender: str, content: str, timestamp: str):
        """添加消息到显示区域"""
        self._message_count += 1
        self._update_message_count()

        # 转义HTML特殊字符
        content_escaped = html.escape(content)
        sender_escaped = html.escape(sender)
        timestamp_escaped = html.escape(timestamp)

        # 根据消息类型设置不同样式
        if msg_type == "user":
            message_html = f"""
            <div style="margin: 8px 0; text-align: right;">
                <div style="background: linear-gradient(135deg, #007AFF, #0056CC); color: white;
                           display: inline-block; padding: 8px 12px; border-radius: 18px;
                           max-width: 70%; word-wrap: break-word; margin-right: 8px;
                           box-shadow: 0 2px 6px rgba(0, 122, 255, 0.3);">
                    {content_escaped}
                </div>
                <div style="font-size: 10px; color: #888; margin-top: 2px; margin-right: 8px;">
                    {sender_escaped} {timestamp_escaped}
                </div>
            </div>
            """
        elif msg_type == "ai":
            message_html = f"""
            <div style="margin: 8px 0; text-align: left;">
                <div style="background-color: #f5f5f5; color: #333; display: inline-block;
                           padding: 8px 12px; border-radius: 18px; max-width: 70%;
                           word-wrap: break-word; margin-left: 8px;
                           border: 1px solid #e8e8e8; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                    {content_escaped}
                </div>
                <div style="font-size: 10px; color: #888; margin-top: 2px; margin-left: 8px;">
                    {sender_escaped} {timestamp_escaped}
                </div>
            </div>
            """
        else:  # system
            message_html = f"""
            <div style="margin: 5px 0; text-align: center;">
                <div style="background-color: rgba(255, 243, 205, 0.8); color: #856404;
                           display: inline-block; padding: 4px 10px; border-radius: 12px;
                           font-size: 11px; border: 1px solid rgba(255, 234, 167, 0.8);
                           box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);">
                    [{timestamp_escaped}] {content_escaped}
                </div>
            </div>
            """

        # 插入消息
        cursor = self._chat_browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(message_html)

        # 自动滚动到底部
        if self._auto_scroll:
            self._scroll_to_bottom()

        logger.debug(f"添加{msg_type}消息: {content[:30]}...")

    def _update_message_count(self):
        """更新消息计数显示"""
        self._message_count_label.setText(f"聊天记录: {self._message_count}条")

    def _scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self._chat_browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_history(self):
        """清空对话历史"""
        self._chat_browser.clear()
        self._message_count = 0
        self._update_message_count()
        logger.info("对话历史已清空")

        # 添加欢迎消息
        self.add_system_message("聊天记录已清空 - 小智AI准备就绪")

    def set_font_size(self, size: int):
        """设置字体大小"""
        font = self._chat_browser.font()
        font.setPointSize(size)
        self._chat_browser.setFont(font)
        logger.debug(f"字体大小设置为: {size}")

    def export_chat_history(self) -> str:
        """导出对话历史为文本"""
        return self._chat_browser.toPlainText()

    def search_in_history(self, text: str) -> bool:
        """在对话历史中搜索文本"""
        if not text:
            return False

        # 使用QTextBrowser的查找功能
        found = self._chat_browser.find(text)
        if found:
            logger.debug(f"在对话历史中找到: {text}")
        else:
            logger.debug(f"在对话历史中未找到: {text}")
        return found

    def get_message_count(self) -> int:
        """获取消息数量"""
        return self._message_count

    def set_visible(self, visible: bool):
        """设置组件可见性"""
        self.setVisible(visible)
        if visible and self._auto_scroll:
            # 显示时自动滚动到底部
            QTimer.singleShot(100, self._scroll_to_bottom)