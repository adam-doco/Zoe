# 小智AI客户端UI重设计方案

## 🎨 设计概述

基于用户提供的参考图片和需求，对Zoev3客户端的聊天输入界面进行现代化重设计。

## 📐 当前界面分析

### 现有布局 (gui_display.ui:409-546)
```
[5, 735, 790, 40] - floating_controls
  ├── [按住后说话] [打断对话] [文字输入框] [发送] [开始对话] [手动对话] [参数配置]
```

### 现有问题
- 按钮样式过于方正，缺乏现代感
- 元素排列过于紧密，缺乏呼吸感
- 所有控件都在同一水平线上，视觉层次不明确

## 🎯 新设计目标

### 视觉风格
- **圆润设计**：所有按钮和输入框采用圆角设计 (border-radius: 20px+)
- **现代感**：使用渐变色、阴影等现代UI元素
- **分层布局**：不同功能区域分层次排列

### 功能分区

#### 1. 主要输入区域 (底部中央)
```
[🎤 语音] [💬 文字输入框................] [📤 发送]
```
- **位置**: 底部中央，水平居中
- **尺寸**: 占总宽度的70%左右 (~550px)
- **样式**: 圆角输入框，左右两侧圆角按钮

#### 2. 次要控制区域 (右上角)
```
[手动对话] [⚙️ 参数配置]
```
- **位置**: 窗口右上角
- **样式**: 小圆角按钮，透明背景

#### 3. 状态控制区域 (左下角附近)
```
[打断对话]
```
- **位置**: 主输入区域左侧
- **样式**: 警告色圆角按钮

## 🎨 详细设计规范

### 颜色系统
```css
/* 主色调 */
--primary-blue: #007AFF;
--primary-blue-hover: #0056CC;
--primary-blue-active: #004099;

/* 输入框 */
--input-bg: rgba(255, 255, 255, 0.95);
--input-border: rgba(0, 0, 0, 0.1);
--input-focus: #007AFF;

/* 语音按钮 */
--voice-bg: #34C759;
--voice-hover: #28A745;

/* 发送按钮 */
--send-bg: #007AFF;
--send-hover: #0056CC;

/* 打断按钮 */
--interrupt-bg: #FF3B30;
--interrupt-hover: #E52E24;

/* 次要按钮 */
--secondary-bg: rgba(255, 255, 255, 0.8);
--secondary-text: #666666;
```

### 尺寸规范
```css
/* 主输入区域 */
--main-input-height: 50px;
--main-input-radius: 25px;

/* 按钮 */
--button-height: 45px;
--button-radius: 22px;
--small-button-height: 32px;
--small-button-radius: 16px;

/* 间距 */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 16px;
--spacing-lg: 24px;
```

## 📍 具体布局坐标

### 新布局规划 (800x800窗口)
```
┌─────────────────────────────────────────────────────────────────────────┐
│ [状态: 未连接]                          [手动对话] [⚙️ 参数配置] │ y:5-35
│                                                                     │
│                                                                     │
│                      Live2D 显示区域                                 │ y:35-720
│                         (全屏)                                       │
│                                                                     │
│                                                                     │
│ [打断对话]     [🎤] [文字输入框..................] [📤]              │ y:730-780
└─────────────────────────────────────────────────────────────────────────┘
   x:20        x:150                               x:650  x:700
```

### 具体坐标配置
```xml
<!-- 右上角控制区 -->
<widget class="QFrame" name="top_right_controls">
  <property name="geometry">
    <rect>
      <x>600</x> <y>5</y>
      <width>190</width> <height>35</height>
    </rect>
  </property>
</widget>

<!-- 主输入区域 -->
<widget class="QFrame" name="main_input_area">
  <property name="geometry">
    <rect>
      <x>150</x> <y>730</y>
      <width>550</width> <height>50</height>
    </rect>
  </property>
</widget>

<!-- 打断按钮 -->
<widget class="QPushButton" name="interrupt_btn">
  <property name="geometry">
    <rect>
      <x>20</x> <y>735</y>
      <width>120</width> <height>40</height>
    </rect>
  </property>
</widget>
```

## 🎨 样式表设计

### 主输入区域样式
```css
/* 容器 */
QFrame#main_input_area {
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 25px;
    border: 1px solid rgba(0, 0, 0, 0.1);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 语音按钮 */
QPushButton#voice_btn {
    background-color: #34C759;
    color: white;
    border: none;
    border-radius: 22px;
    font-size: 14px;
    font-weight: 600;
    min-width: 80px;
    height: 44px;
}

QPushButton#voice_btn:hover {
    background-color: #28A745;
}

/* 文字输入框 */
QLineEdit#text_input {
    background-color: transparent;
    border: none;
    font-size: 14px;
    padding: 0 16px;
    color: #333333;
}

QLineEdit#text_input:focus {
    border: 2px solid #007AFF;
    border-radius: 20px;
}

/* 发送按钮 */
QPushButton#send_btn {
    background-color: #007AFF;
    color: white;
    border: none;
    border-radius: 22px;
    font-size: 14px;
    font-weight: 600;
    min-width: 80px;
    height: 44px;
}

QPushButton#send_btn:hover {
    background-color: #0056CC;
}
```

### 次要控制区样式
```css
/* 右上角按钮 */
QPushButton#mode_btn, QPushButton#settings_btn {
    background-color: rgba(255, 255, 255, 0.8);
    color: #666666;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 16px;
    font-size: 12px;
    padding: 8px 16px;
    height: 32px;
}

QPushButton#mode_btn:hover, QPushButton#settings_btn:hover {
    background-color: rgba(255, 255, 255, 0.95);
    color: #333333;
}
```

### 打断按钮样式
```css
QPushButton#interrupt_btn {
    background-color: #FF3B30;
    color: white;
    border: none;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 600;
    height: 40px;
}

QPushButton#interrupt_btn:hover {
    background-color: #E52E24;
}
```

## 🚀 实施步骤

1. **修改UI布局文件** (gui_display.ui)
   - 删除现有floating_controls布局
   - 创建新的分区布局结构
   - 设置正确的坐标和尺寸

2. **更新样式表**
   - 应用圆角设计
   - 添加现代化颜色和阴影
   - 优化交互状态

3. **更新Python代码**
   - 适配新的UI元素名称
   - 保持现有功能逻辑不变

4. **测试验证**
   - 确保所有按钮功能正常
   - 验证响应式布局
   - 测试视觉效果

## 📝 注意事项

- **保持功能完整性**：UI重设计不能影响现有功能
- **响应式适配**：考虑不同窗口大小的适配
- **性能优化**：避免过重的视觉效果影响性能
- **用户体验**：确保按钮大小适合点击操作

---

*该设计方案旨在提供现代化、用户友好的界面，同时保持原有功能的完整性。*