#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小智AI Python客户端 - 完整设备激活和WebSocket连接实现
基于iOS项目CLAUDE.md规范，严格按照状态机流程执行

功能包括：
1. 虚拟设备生成 (02:00:00:xx:xx:xx格式MAC + UUID + 序列号 + HMAC密钥)
2. OTA配置请求 (获取6位验证码或直接授权)
3. 激活状态轮询 (HMAC签名验证，最多60次×5秒间隔)
4. WebSocket连接建立 (Hello握手 + 二进制JSON探测 + 心跳重连)
5. 实时语音播放 (Opus解码 + 音频播放 - 可以听到小智AI语音)

依赖安装：
pip install aiohttp websockets pyaudio opuslib

注意：
- pyaudio 用于音频播放输出
- opuslib 用于Opus音频解码  
- 没有这两个依赖也能正常聊天，只是听不到语音
"""

import asyncio
import json
import hashlib
import hmac
import logging
import os
import random
import secrets
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum, auto
from typing import Dict, Any, Optional, Callable, Union, List
from urllib.parse import urlparse

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

# 音频播放相关依赖
try:
    import pyaudio
    import wave
    import io
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("⚠️ 音频播放功能不可用，请安装依赖: pip install pyaudio")

# OPUS解码依赖 - 小智AI强制要求OPUS格式
OPUS_AVAILABLE = False
OPUS_DECODER = None

# 小智AI音频规范：
# - 协议版本: 1
# - 传输方式: Websocket
# - 音频格式: OPUS (强制)
# - 音频参数: 采样率16000Hz, 通道数1, 帧长60ms

try:
    import opuslib
    OPUS_AVAILABLE = True
    OPUS_DECODER = "opuslib"
    print("✅ OPUS解码器可用 (小智AI强制要求)")
except ImportError:
    print("❌ OPUS解码器不可用，请安装: pip install opuslib")
    print("❌ 小智AI强制要求OPUS格式，没有回退方案")
    OPUS_AVAILABLE = False
except Exception as e:
    print(f"❌ OPUS解码器初始化失败: {e}")
    OPUS_AVAILABLE = False

if not OPUS_AVAILABLE:
    print("❌ 无法继续：小智AI要求OPUS音频格式")
    print("💡 解决方案: pip install opuslib")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ================================
# 数据结构定义
# ================================

class DeviceState(Enum):
    """设备状态枚举 - 严格按照CLAUDE.md状态机"""
    UNINITIALIZED = "uninitialized"       # 初始状态
    PENDING_ACTIVATION = "pendingActivation"  # 等待激活中
    ACTIVATED = "activated"                # 已激活
    WS_CONNECTING = "wsConnecting"         # WebSocket连接中
    WS_READY = "wsReady"                  # WebSocket已就绪
    STREAMING = "streaming"                # 音频流传输中

class ActivationStage(Enum):
    """激活阶段枚举"""
    IDLE = "idle"
    NEED_CODE = "needCode"
    POLLING = "polling"
    ACTIVATED = "activated"

@dataclass
class DeviceIdentity:
    """设备身份数据结构"""
    device_id: str          # 02:00:00:xx:xx:xx
    client_id: str          # UUID v4
    serial: str             # SN-XXXXXXXX-XXXXXXXXXXXX
    hmac_key_hex: str       # 64-char hex
    activated: bool = False

@dataclass
class EndpointConfig:
    """端点配置"""
    ota_base: str = "https://api.tenclass.net/xiaozhi/"
    origin: str = "https://xiaozhi.me"  # 固定值，大小写严格

    def validate_websocket_url(self, url: str) -> bool:
        """验证WebSocket URL格式"""
        has_trailing_slash = url.endswith("/")
        logger.info(f"[CFG] ws={url} slash={has_trailing_slash}")
        
        if not has_trailing_slash:
            logger.error("❌ WebSocket URL 必须以 / 结尾")
            return False
        
        return True

@dataclass
class WebSocketConfig:
    """WebSocket配置"""
    url: str
    token: str

@dataclass
class ActivationData:
    """激活数据"""
    code: str           # 6位验证码
    challenge: str      # 服务器challenge
    timeout_ms: Optional[int] = None

@dataclass
class OTAResponse:
    """OTA响应"""
    websocket: Optional[WebSocketConfig] = None
    activation: Optional[ActivationData] = None

# ================================
# 音频播放相关类
# ================================

class AudioPlayer:
    """实时音频播放器 - 支持Opus解码和PCM播放"""
    
    def __init__(self):
        self.is_playing = False
        self.audio_stream = None
        self.pyaudio_instance = None
        self.opus_decoder = None
        self.sample_rate = 16000  # 小智AI强制要求采样率
        self.channels = 1        # 单声道
        self.audio_queue = asyncio.Queue()
        self.play_task = None
        
        if OPUS_AVAILABLE:
            try:
                # 创建Opus解码器 (24kHz, 单声道)
                self.opus_decoder = opuslib.Decoder(fs=self.sample_rate, channels=self.channels)
                logger.info(f"[AUDIO] Opus解码器初始化成功: {self.sample_rate}Hz, {self.channels}声道")
            except Exception as e:
                logger.error(f"[AUDIO] Opus解码器初始化失败: {e}")
                self.opus_decoder = None
        
        if AUDIO_AVAILABLE:
            try:
                # 初始化PyAudio
                self.pyaudio_instance = pyaudio.PyAudio()
                logger.info("[AUDIO] PyAudio初始化成功")
            except Exception as e:
                logger.error(f"[AUDIO] PyAudio初始化失败: {e}")
                self.pyaudio_instance = None
    
    def start_playback(self):
        """启动音频播放"""
        if not AUDIO_AVAILABLE or not self.pyaudio_instance:
            logger.warning("[AUDIO] 音频播放不可用")
            return False
        
        if self.is_playing:
            return True
        
        try:
            # 创建音频流 (播放用)
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,    # 16位PCM
                channels=self.channels,     # 单声道
                rate=self.sample_rate,      # 24kHz (小智AI下行)
                output=True,               # 播放流
                frames_per_buffer=1024,    # 缓冲区大小
                stream_callback=None       # 非回调模式，手动写入
            )
            
            self.is_playing = True
            
            # 启动播放任务
            self.play_task = asyncio.create_task(self._audio_playback_loop())
            
            logger.info(f"[AUDIO] 音频播放启动: {self.sample_rate}Hz, {self.channels}声道")
            return True
            
        except Exception as e:
            logger.error(f"[AUDIO] 音频播放启动失败: {e}")
            return False
    
    def stop_playback(self):
        """停止音频播放"""
        self.is_playing = False
        
        if self.play_task:
            self.play_task.cancel()
            self.play_task = None
        
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_stream = None
            except:
                pass
        
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                break
        
        logger.info("[AUDIO] 音频播放已停止")
    
    async def play_opus_data(self, opus_data: bytes):
        """播放Opus音频数据"""
        if not OPUS_AVAILABLE:
            logger.warning("[AUDIO] Opus解码器不可用")
            return
            
        if not self.is_playing:
            # 自动启动播放
            if not self.start_playback():
                logger.error("[AUDIO] 无法启动音频播放")
                return
        
        logger.info(f"[AUDIO] 准备播放Opus数据: {len(opus_data)} bytes")
        
        # 将Opus数据加入播放队列
        try:
            await self.audio_queue.put(opus_data)
            queue_size = self.audio_queue.qsize() if hasattr(self.audio_queue, 'qsize') else 0
            logger.info(f"[AUDIO] 音频数据已入队，当前队列大小: {queue_size}")
        except Exception as e:
            logger.error(f"[AUDIO] 音频数据入队失败: {e}")
    
    async def _audio_playback_loop(self):
        """音频播放循环"""
        logger.info("[AUDIO] 音频播放循环启动")
        
        try:
            while self.is_playing:
                try:
                    # 从队列获取Opus数据 (超时1秒)
                    opus_data = await asyncio.wait_for(
                        self.audio_queue.get(), 
                        timeout=1.0
                    )
                    
                    # 解码Opus到PCM
                    logger.info(f"[AUDIO] 解码Opus数据: {len(opus_data)} bytes")
                    pcm_data = self._decode_opus_to_pcm(opus_data)
                    if pcm_data:
                        logger.info(f"[AUDIO] 解码成功，PCM数据: {len(pcm_data)} bytes")
                        # 播放PCM数据
                        self._play_pcm_data(pcm_data)
                    else:
                        logger.error(f"[AUDIO] Opus解码失败")
                        
                except asyncio.TimeoutError:
                    # 队列空闲，继续等待
                    continue
                    
                except asyncio.CancelledError:
                    logger.info("[AUDIO] 播放循环被取消")
                    break
                    
                except Exception as e:
                    logger.error(f"[AUDIO] 播放循环错误: {e}")
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"[AUDIO] 播放循环异常: {e}")
        
        logger.info("[AUDIO] 音频播放循环结束")
    
    def _decode_opus_to_pcm(self, opus_data: bytes) -> Optional[bytes]:
        """解码Opus数据到PCM"""
        if not self.opus_decoder:
            logger.debug("[AUDIO] Opus解码器不可用，跳过解码")
            return None
        
        try:
            # 根据当前采样率计算正确的frame_size
            # 小智AI使用60ms帧长度
            frame_size = int(self.sample_rate * 0.06)  # 60ms
            logger.info(f"[AUDIO] 使用frame_size: {frame_size} (采样率: {self.sample_rate}Hz)")
            
            # Opus解码到PCM (16位整数)
            pcm_data = self.opus_decoder.decode(opus_data, frame_size=frame_size)
            return pcm_data
            
        except Exception as e:
            logger.debug(f"[AUDIO] Opus解码失败: {e}")
            return None
    
    def _play_pcm_data(self, pcm_data: bytes):
        """播放PCM数据"""
        if not self.audio_stream:
            logger.error("[AUDIO] 音频流未初始化")
            return
        if not self.is_playing:
            logger.error("[AUDIO] 播放器未启动")
            return
        
        try:
            logger.info(f"[AUDIO] 播放PCM数据: {len(pcm_data)} bytes")
            # 直接写入音频流播放
            self.audio_stream.write(pcm_data)
            logger.info("[AUDIO] PCM数据已写入音频流")
            
        except Exception as e:
            logger.debug(f"[AUDIO] PCM播放失败: {e}")
    
    def update_sample_rate(self, new_sample_rate: int):
        """更新采样率 (需要重新启动播放器)"""
        if self.sample_rate == new_sample_rate:
            return
        
        logger.info(f"[AUDIO] 更新采样率: {self.sample_rate}Hz → {new_sample_rate}Hz")
        
        # 保存播放状态
        was_playing = self.is_playing
        
        # 停止当前播放
        if self.is_playing:
            self.stop_playback()
        
        # 更新采样率
        self.sample_rate = new_sample_rate
        
        # 重新创建Opus解码器
        if OPUS_AVAILABLE:
            try:
                self.opus_decoder = opuslib.Decoder(fs=self.sample_rate, channels=self.channels)
                logger.info(f"[AUDIO] Opus解码器已更新: {self.sample_rate}Hz")
            except Exception as e:
                logger.error(f"[AUDIO] Opus解码器更新失败: {e}")
                self.opus_decoder = None
        
        # 恢复播放状态
        if was_playing:
            self.start_playback()
    
    def get_audio_info(self):
        """获取音频信息"""
        return {
            "playing": self.is_playing,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "queue_size": self.audio_queue.qsize() if hasattr(self.audio_queue, 'qsize') else 0,
            "opus_available": self.opus_decoder is not None,
            "pyaudio_available": self.pyaudio_instance is not None
        }
    
    def cleanup(self):
        """清理资源"""
        self.stop_playback()
        
        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
            except:
                pass
        
        logger.info("[AUDIO] 音频播放器资源已清理")

# ================================
# 工具类
# ================================

class SensitiveDataMasker:
    """敏感数据脱敏工具"""
    
    @staticmethod
    def mask(data: str, show_chars: int = 4) -> str:
        """脱敏显示：显示前后指定字符数"""
        if len(data) <= show_chars * 2:
            return "****"
        return f"{data[:show_chars]}****{data[-show_chars:]}"
    
    @staticmethod
    def mask_uuid(uuid_str: str) -> str:
        """脱敏UUID：显示前4+后4"""
        if len(uuid_str) < 8:
            return "****"
        return f"{uuid_str[:4]}****{uuid_str[-4:]}"
    
    @staticmethod
    def display_verification_code(code: str) -> str:
        """验证码完整显示（用户需要输入）"""
        return code

class SecureStore:
    """安全存储 - 简化文件版本（生产环境应使用操作系统密钥库）"""
    
    _store_file = "xiaozhi_device.json"
    
    @classmethod
    def get(cls, key: str) -> Optional[str]:
        """获取存储值"""
        try:
            if os.path.exists(cls._store_file):
                with open(cls._store_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get(key)
        except Exception as e:
            logger.error(f"读取存储失败: {e}")
        return None
    
    @classmethod
    def set(cls, key: str, value: str) -> None:
        """设置存储值"""
        try:
            data = {}
            if os.path.exists(cls._store_file):
                with open(cls._store_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            data[key] = value
            
            with open(cls._store_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存存储失败: {e}")
    
    @classmethod
    def remove(cls, key: str) -> None:
        """删除存储值"""
        try:
            if os.path.exists(cls._store_file):
                with open(cls._store_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if key in data:
                    del data[key]
                    
                with open(cls._store_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"删除存储失败: {e}")
    
    @classmethod
    def clear_all(cls) -> None:
        """清空所有存储"""
        try:
            if os.path.exists(cls._store_file):
                os.remove(cls._store_file)
            logger.warning("[EFUSE] ⚠️ 完全重置所有设备身份和状态")
        except Exception as e:
            logger.error(f"清空存储失败: {e}")

class PersistKey:
    """存储键定义"""
    DEVICE_ID = "device_id"
    CLIENT_ID = "client_id"
    SERIAL = "serial"
    HMAC_KEY = "hmac_key"
    ACTIVATED = "activated"
    WEBSOCKET_URL = "websocket_url"
    WEBSOCKET_TOKEN = "websocket_token"

class Crypto:
    """加密工具"""
    
    @staticmethod
    def hmac_sha256_hex(key_hex: str, data: str) -> str:
        """计算HMAC-SHA256签名"""
        try:
            # 将十六进制密钥转换为字节
            key_bytes = bytes.fromhex(key_hex)
            # 计算HMAC
            signature = hmac.new(key_bytes, data.encode('utf-8'), hashlib.sha256)
            return signature.hexdigest()
        except Exception as e:
            logger.error(f"HMAC计算失败: {e}")
            return ""

# ================================
# 核心管理类
# ================================

class IdentityManager:
    """设备身份管理器 - 严格按照CLAUDE.md I.3.2规范实现"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def current(self, force_new: bool = False) -> DeviceIdentity:
        """获取当前设备身份，支持强制重新生成"""
        if not force_new:
            # 尝试从存储加载现有身份
            device_id = SecureStore.get(PersistKey.DEVICE_ID)
            client_id = SecureStore.get(PersistKey.CLIENT_ID)
            serial = SecureStore.get(PersistKey.SERIAL)
            hmac_key = SecureStore.get(PersistKey.HMAC_KEY)
            activated_str = SecureStore.get(PersistKey.ACTIVATED)
            
            if all([device_id, client_id, serial, hmac_key]):
                activated = activated_str == "true"
                return DeviceIdentity(
                    device_id=device_id,
                    client_id=client_id,
                    serial=serial,
                    hmac_key_hex=hmac_key,
                    activated=activated
                )
        
        # 生成新身份
        if force_new:
            logger.info("[EFUSE] FORCE_NEW_ID=1 触发")
            self.clear_activation_state()
        
        device_id = self._generate_virtual_mac()
        client_id = str(uuid.uuid4())
        serial = self._generate_serial(device_id)
        hmac_key = self._random_hex(32)
        
        identity = DeviceIdentity(
            device_id=device_id,
            client_id=client_id,
            serial=serial,
            hmac_key_hex=hmac_key,
            activated=False
        )
        
        # 保存到安全存储
        SecureStore.set(PersistKey.DEVICE_ID, device_id)
        SecureStore.set(PersistKey.CLIENT_ID, client_id)
        SecureStore.set(PersistKey.SERIAL, serial)
        SecureStore.set(PersistKey.HMAC_KEY, hmac_key)
        SecureStore.set(PersistKey.ACTIVATED, "false")
        
        logger.info(f"[EFUSE] 重新生成: mac={device_id} clientId={SensitiveDataMasker.mask_uuid(client_id)}")
        logger.info("[STATE] → PendingActivation")
        
        return identity
    
    def _generate_virtual_mac(self) -> str:
        """生成虚拟MAC地址 - 02:00:00:xx:xx:xx格式"""
        def random_byte() -> str:
            return f"{random.randint(0, 255):02x}"
        
        return f"02:00:00:{random_byte()}:{random_byte()}:{random_byte()}"
    
    def _generate_serial(self, mac: str) -> str:
        """生成设备序列号"""
        seed = ''.join(f"{random.randint(0, 255):02X}" for _ in range(4))
        mac_hex = mac.replace(':', '').upper()
        tail = mac_hex[-12:] if len(mac_hex) >= 12 else mac_hex.ljust(12, '0')
        return f"SN-{seed}-{tail}"
    
    def _random_hex(self, bytes_count: int) -> str:
        """生成随机十六进制字符串"""
        return secrets.token_hex(bytes_count)
    
    def is_activated(self) -> bool:
        """检查设备是否已激活"""
        return SecureStore.get(PersistKey.ACTIVATED) == "true"
    
    def mark_as_activated(self) -> None:
        """标记设备为已激活"""
        SecureStore.set(PersistKey.ACTIVATED, "true")
        logger.info("[EFUSE] 标记设备已激活")
    
    def clear_activation_state(self) -> None:
        """清空激活状态"""
        SecureStore.remove(PersistKey.ACTIVATED)
        SecureStore.remove(PersistKey.WEBSOCKET_URL)
        SecureStore.remove(PersistKey.WEBSOCKET_TOKEN)
        logger.info("[EFUSE] 清空激活状态")
    
    def reset_all(self) -> None:
        """完全重置所有身份和状态（调试用，慎用）"""
        SecureStore.clear_all()

class DeviceStateManager:
    """设备状态管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_state = DeviceState.UNINITIALIZED
        return cls._instance
    
    def transition(self, to_state: DeviceState) -> None:
        """状态转换"""
        logger.info(f"[STATE] {self.current_state.value} → {to_state.value}")
        self.current_state = to_state
    
    def can_connect_websocket(self) -> bool:
        """检查是否可以连接WebSocket"""
        return self.current_state in [DeviceState.ACTIVATED, DeviceState.WS_CONNECTING, DeviceState.WS_READY]
    
    def can_send_websocket_data(self) -> bool:
        """检查是否可以发送WebSocket数据"""
        return self.current_state in [DeviceState.WS_READY, DeviceState.STREAMING]

class OTAManager:
    """OTA管理器 - 负责设备激活和配置获取"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def request_config(
        self,
        endpoint: EndpointConfig,
        device_id: str,
        client_id: str
    ) -> OTAResponse:
        """请求OTA配置"""
        url = f"{endpoint.ota_base}ota/"
        
        # 获取当前身份
        identity = IdentityManager().current()
        
        # 构建请求头
        headers = {
            "Device-Id": device_id,
            "Client-Id": client_id,
            "Activation-Version": "2",
            "Content-Type": "application/json",
            "User-Agent": "board_type/xiaozhi-python-1.0",
            "Accept-Language": "zh-CN"
        }
        
        # 构建请求体
        request_body = {
            "application": {
                "version": "1.0.0",
                "elf_sha256": identity.hmac_key_hex
            },
            "board": {
                "type": "xiaozhi-python",
                "name": "xiaozhi-python",
                "ip": "0.0.0.0",
                "mac": device_id
            }
        }
        
        logger.info(f"[OTA] 请求配置: {url}")
        logger.debug(f"[OTA] Device-Id: {device_id}")
        logger.debug(f"[OTA] Client-Id: {SensitiveDataMasker.mask_uuid(client_id)}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=request_body) as response:
                    logger.info(f"[OTA] HTTP {response.status}")
                    
                    response_data = await response.json()
                    return self._parse_ota_response(response_data)
                    
        except Exception as e:
            logger.error(f"[OTA] 网络错误: {e}")
            raise
    
    async def poll_activate(
        self,
        endpoint: EndpointConfig,
        serial: str,
        challenge: str,
        hmac_hex: str
    ) -> str:
        """轮询激活状态"""
        # 参数验证
        if not serial or not challenge or not hmac_hex:
            logger.error(f"[ACT] ❌ 激活参数不完整: serial={bool(serial)} challenge={bool(challenge)} hmac={bool(hmac_hex)}")
            raise Exception("activation_params_incomplete")
        
        url = f"{endpoint.ota_base}ota/activate"
        
        identity = IdentityManager().current()
        
        # 设置请求头
        headers = {
            "Activation-Version": "2",
            "Device-Id": identity.device_id,
            "Client-Id": identity.client_id,
            "Content-Type": "application/json"
        }
        
        # 构建请求体 - 严格按照iOS ActivationRequest格式
        activation_request = {
            "Payload": {
                "algorithm": "hmac-sha256",
                "serial_number": serial,
                "challenge": challenge,
                "hmac": hmac_hex
            }
        }
        
        logger.debug(f"[ACT] 轮询激活: serial={SensitiveDataMasker.mask(serial)}")
        logger.debug(f"[ACT] 请求体: {json.dumps(activation_request, indent=2)}")
        logger.debug(f"[ACT] 请求头: {headers}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=activation_request) as response:
                    logger.debug(f"[ACT] 激活响应 HTTP {response.status}")
                    
                    if response.status == 200:
                        # 激活成功
                        try:
                            response_data = await response.json()
                            device_id = response_data.get("device_id", "activated")
                            logger.info(f"[ACT] ✅ HTTP 200 Device activated device_id={device_id}")
                            return device_id
                        except:
                            logger.info("[ACT] ✅ HTTP 200 Device activated")
                            return "activated"
                    
                    elif response.status == 202:
                        # 继续等待用户输入
                        logger.debug("[ACT] HTTP 202 等待用户在官网输入验证码...")
                        raise Exception("activation_timeout")
                    
                    else:
                        # 激活失败
                        error_text = await response.text()
                        logger.error(f"[ACT] 激活失败: HTTP {response.status}")
                        logger.error(f"[ACT] 错误详情: {error_text}")
                        
                        # 检查是否是serial_number相关错误
                        if "serial_number" in error_text.lower() or "序列号" in error_text:
                            logger.error(f"[ACT] ❌ 序列号相关错误，检查设备序列号: {identity.serial}")
                        
                        raise Exception(f"activation_failed: HTTP {response.status} - {error_text}")
                        
        except Exception as e:
            if "activation_timeout" in str(e):
                raise e
            logger.error(f"[ACT] 激活请求网络错误: {e}")
            raise
    
    def _parse_ota_response(self, json_data: dict) -> OTAResponse:
        """解析OTA响应数据"""
        websocket = None
        activation = None
        
        # 解析WebSocket配置 (分支B: 直接授权)
        if "websocket" in json_data:
            ws_dict = json_data["websocket"]
            if "url" in ws_dict and "token" in ws_dict:
                websocket = WebSocketConfig(
                    url=ws_dict["url"],
                    token=ws_dict["token"]
                )
                logger.info("[OTA] 分支B：直接授权，获得WebSocket配置")
        
        # 解析激活数据 (分支A: 需要验证码)
        if "activation" in json_data:
            act_dict = json_data["activation"]
            if "code" in act_dict and "challenge" in act_dict:
                activation = ActivationData(
                    code=act_dict["code"],
                    challenge=act_dict["challenge"],
                    timeout_ms=act_dict.get("timeout_ms")
                )
                logger.info(f"[OTA] 分支A：需要激活，验证码={activation.code}")
        
        return OTAResponse(websocket=websocket, activation=activation)

class Activator:
    """激活器 - 严格按照CLAUDE.md I.3.3规范实现激活门禁与流程"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_stage = ActivationStage.IDLE
            cls._instance.is_activating = False
            cls._instance.current_endpoint = None
        return cls._instance
    
    async def ensure_activated(
        self,
        endpoint: EndpointConfig,
        force_new: bool = False
    ) -> tuple[ActivationStage, Optional[str], Optional[str]]:
        """确保设备已激活 - 硬性门禁检查
        
        Returns:
            (stage, code, challenge) - stage为激活阶段，code和challenge仅在需要验证码时有值
        """
        # 保存endpoint配置供后续使用
        self.current_endpoint = endpoint
        
        # 如果强制重新激活，清理旧状态
        if force_new:
            logger.warning("[GATE] FORCE_NEW_ID=1 触发，重新生成设备身份")
            IdentityManager().reset_all()
            DeviceStateManager().transition(DeviceState.UNINITIALIZED)
        
        identity = IdentityManager().current(force_new=force_new)
        
        # 检查本地激活状态
        if not force_new and identity.activated:
            logger.info("[GATE] 设备已激活，跳过激活流程")
            self.current_stage = ActivationStage.ACTIVATED
            DeviceStateManager().transition(DeviceState.ACTIVATED)
            return ActivationStage.ACTIVATED, None, None
        
        # 更新状态为等待激活
        DeviceStateManager().transition(DeviceState.PENDING_ACTIVATION)
        self.is_activating = True
        
        # 调用OTA获取配置
        logger.info("[OTA] 开始OTA配置请求...")
        try:
            ota_manager = OTAManager()
            response = await ota_manager.request_config(
                endpoint=endpoint,
                device_id=identity.device_id,
                client_id=identity.client_id
            )
            
            return await self._handle_ota_response(response, endpoint)
            
        except Exception as e:
            logger.error(f"[OTA] 配置请求失败: {e}")
            self.is_activating = False
            raise
    
    async def _handle_ota_response(
        self,
        response: OTAResponse,
        endpoint: EndpointConfig
    ) -> tuple[ActivationStage, Optional[str], Optional[str]]:
        """处理OTA响应 - 分支A和分支B"""
        if response.activation:
            # 分支A：需要验证码激活
            return await self._handle_activation_required(response.activation, endpoint)
            
        elif response.websocket:
            # 分支B：直接授权（设备已在服务端激活）
            return await self._handle_direct_authorization(response.websocket)
            
        else:
            logger.error("[OTA] 无效的OTA响应，既无WebSocket配置也无激活信息")
            self.is_activating = False
            raise Exception("invalid_ota_response")
    
    async def _handle_direct_authorization(
        self,
        websocket: WebSocketConfig
    ) -> tuple[ActivationStage, Optional[str], Optional[str]]:
        """处理分支B：直接授权"""
        logger.info("[ACT] 分支B：服务端已认证设备，直接保存配置")
        
        # 保存WebSocket配置
        SecureStore.set(PersistKey.WEBSOCKET_URL, websocket.url)
        SecureStore.set(PersistKey.WEBSOCKET_TOKEN, websocket.token)
        
        # 标记为已激活
        IdentityManager().mark_as_activated()
        
        # 更新状态
        self.current_stage = ActivationStage.ACTIVATED
        DeviceStateManager().transition(DeviceState.ACTIVATED)
        self.is_activating = False
        
        return ActivationStage.ACTIVATED, None, None
    
    async def _handle_activation_required(
        self,
        activation: ActivationData,
        endpoint: EndpointConfig
    ) -> tuple[ActivationStage, Optional[str], Optional[str]]:
        """处理分支A：需要验证码激活"""
        logger.info("[ACT] 分支A：需要验证码激活")
        logger.info(f"[ACT] code={SensitiveDataMasker.display_verification_code(activation.code)} challenge={SensitiveDataMasker.mask(activation.challenge)}")
        
        # 更新状态为需要验证码
        self.current_stage = ActivationStage.NEED_CODE
        
        # 返回验证码给调用方显示
        return ActivationStage.NEED_CODE, activation.code, activation.challenge
    
    async def submit_activation(
        self,
        endpoint: EndpointConfig,
        challenge: str
    ) -> bool:
        """提交激活请求 - 用户在官网输入验证码后调用"""
        identity = IdentityManager().current()
        
        logger.info("[ACT] 开始激活轮询...")
        self.current_stage = ActivationStage.POLLING
        
        # 计算HMAC签名
        hmac_signature = Crypto.hmac_sha256_hex(identity.hmac_key_hex, challenge)
        
        # 开始轮询激活状态（最多60次，间隔5秒）
        logger.info(f"[ACT] 开始轮询激活，参数 serial={SensitiveDataMasker.mask(identity.serial)} challenge={SensitiveDataMasker.mask(challenge)} hmac={SensitiveDataMasker.mask(hmac_signature)}")
        
        try:
            await self._poll_activation_status(
                endpoint=endpoint,
                serial=identity.serial,
                challenge=challenge,
                hmac=hmac_signature,
                attempt=1,
                max_attempts=60
            )
            return True
        except Exception as e:
            logger.error(f"[ACT] 激活轮询失败: {e}")
            self.current_stage = ActivationStage.IDLE
            self.is_activating = False
            return False
    
    async def _poll_activation_status(
        self,
        endpoint: EndpointConfig,
        serial: str,
        challenge: str,
        hmac: str,
        attempt: int,
        max_attempts: int
    ) -> None:
        """轮询激活状态 - 递归调用直到成功或超时"""
        logger.debug(f"[ACT] 轮询激活状态 ({attempt}/{max_attempts})")
        
        try:
            ota_manager = OTAManager()
            device_id = await ota_manager.poll_activate(
                endpoint=endpoint,
                serial=serial,
                challenge=challenge,
                hmac_hex=hmac
            )
            
            # 激活成功
            await self._handle_activation_success()
            
        except Exception as e:
            if "activation_timeout" in str(e) and attempt < max_attempts:
                # 继续轮询
                await asyncio.sleep(5.0)
                await self._poll_activation_status(
                    endpoint=endpoint,
                    serial=serial,
                    challenge=challenge,
                    hmac=hmac,
                    attempt=attempt + 1,
                    max_attempts=max_attempts
                )
            else:
                # 轮询失败或达到最大重试次数
                raise e
    
    async def _handle_activation_success(self) -> None:
        """处理激活成功"""
        logger.info("[ACT] ✅ 设备激活成功！")
        
        # 标记为已激活
        IdentityManager().mark_as_activated()
        
        # 激活成功后，重新请求OTA配置获取WebSocket配置
        logger.info("[ACT] 重新请求OTA配置获取WebSocket信息...")
        identity = IdentityManager().current()
        
        if not self.current_endpoint:
            logger.error("[ACT] 缺少endpoint配置")
            self.current_stage = ActivationStage.ACTIVATED
            DeviceStateManager().transition(DeviceState.ACTIVATED)
            self.is_activating = False
            return
        
        try:
            ota_manager = OTAManager()
            response = await ota_manager.request_config(
                endpoint=self.current_endpoint,
                device_id=identity.device_id,
                client_id=identity.client_id
            )
            
            if response.websocket:
                # 现在应该能获得WebSocket配置了
                logger.info(f"[ACT] 获得WebSocket配置 url={response.websocket.url}")
                SecureStore.set(PersistKey.WEBSOCKET_URL, response.websocket.url)
                SecureStore.set(PersistKey.WEBSOCKET_TOKEN, response.websocket.token)
                
                # 更新状态
                self.current_stage = ActivationStage.ACTIVATED
                DeviceStateManager().transition(DeviceState.ACTIVATED)
                self.is_activating = False
            else:
                logger.warning("[ACT] 重新请求后仍无WebSocket配置")
                self.current_stage = ActivationStage.ACTIVATED
                DeviceStateManager().transition(DeviceState.ACTIVATED)
                self.is_activating = False
                
        except Exception as e:
            logger.error(f"[ACT] 重新请求OTA配置失败: {e}")
            self.current_stage = ActivationStage.ACTIVATED
            DeviceStateManager().transition(DeviceState.ACTIVATED)
            self.is_activating = False
    
    def reset_activation(self) -> None:
        """重置激活状态（调试用）"""
        logger.warning("[ACT] ⚠️ 重置激活状态")
        
        IdentityManager().clear_activation_state()
        self.current_stage = ActivationStage.IDLE
        DeviceStateManager().transition(DeviceState.UNINITIALIZED)
        self.is_activating = False

class WebSocketClient:
    """WebSocket客户端 - 严格按照CLAUDE.md M2规范"""
    
    def __init__(self):
        self.connection_state = "disconnected"
        self.session_id: Optional[str] = None
        self.downstream_sample_rate = 16000
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        
        # 二进制JSON缓冲区 - 处理分片
        self.json_buffer = bytearray()
        
        # 重连管理
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_intervals = [1, 2, 4, 8, 15]  # 秒，指数退避，封顶15s
        
        # 心跳管理 - 优化参数，提高稳定性
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.heartbeat_timeout_count = 0
        self.max_heartbeat_timeout = 5  # 增加到5次超时才断开
        self.heartbeat_interval = 45.0  # 增加心跳间隔到45秒
        self.heartbeat_ping_timeout = 15.0  # Ping超时时间15秒

        # 重连需要的连接信息
        self.last_url: Optional[str] = None
        self.last_headers: Optional[Dict[str, str]] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # 回调函数
        self.on_handshake_complete: Optional[Callable[[Optional[str]], None]] = None
        self.on_tts_message: Optional[Callable[[str, Optional[str]], None]] = None
        self.on_emotion: Optional[Callable[[str], None]] = None
        self.on_mcp_message: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_audio_data: Optional[Callable[[bytes], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    async def connect(self, url: str, headers: Dict[str, str]) -> None:
        """连接WebSocket - 严格按照CLAUDE.md门禁检查"""
        # 硬性门禁：检查设备激活状态
        state_manager = DeviceStateManager()
        if not state_manager.can_connect_websocket():
            logger.error("[WS] ❌ 设备未激活，禁止WebSocket连接")
            if self.on_error:
                self.on_error(Exception("device_not_activated"))
            return
        
        # 验证URL格式
        endpoint_config = EndpointConfig()
        if not endpoint_config.validate_websocket_url(url):
            logger.error(f"[WS] ❌ WebSocket URL必须以/结尾: {url}")
            if self.on_error:
                self.on_error(Exception("invalid_url"))
            return
        
        logger.info(f"[HDR] {self._format_headers(headers)}")
        
        self.connection_state = "connecting"
        state_manager.transition(DeviceState.WS_CONNECTING)
        
        logger.info("[WS] connected")
        
        try:
            # 创建WebSocket连接
            self.websocket = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )

            # 保存连接信息用于重连
            self.last_url = url
            self.last_headers = headers.copy()
            self.reconnect_attempts = 0  # 重置重连计数

            # 启动消息监听
            asyncio.create_task(self._listen_messages())
            
            # 发送Hello握手消息
            await asyncio.sleep(0.5)
            await self._send_hello_message()
            
        except Exception as e:
            logger.error(f"[WS] 连接失败: {e}")
            self.connection_state = "error"
            if self.on_error:
                self.on_error(e)
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.connection_state = "disconnected"
        self.session_id = None
        self.reconnect_attempts = 0
        
        logger.info("[WS] 连接已断开")
    
    async def _send_hello_message(self) -> None:
        """发送Hello握手消息"""
        if self.connection_state != "connecting":
            return
        
        hello_message = {
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "features": {
                "mcp": True
            },
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }
        
        try:
            json_string = json.dumps(hello_message)
            logger.info(f"[HELLO][send] len={len(json_string)} variant=v1")
            logger.debug(f"[WS] 发送Hello: {json_string}")
            
            self.connection_state = "handshaking"
            await self.send_message(json_string)
            
        except Exception as e:
            logger.error(f"[HELLO] 编码失败: {e}")
            self.connection_state = "error"
            if self.on_error:
                self.on_error(e)
    
    async def send_message(self, message: Union[str, bytes]) -> None:
        """发送消息 - 硬性门禁检查"""
        if not self.websocket:
            logger.error("[WS] ❌ WebSocket连接不存在")
            return
        
        # 对于二进制数据发送，需要检查就绪状态
        if isinstance(message, bytes):
            state_manager = DeviceStateManager()
            if not state_manager.can_send_websocket_data():
                logger.error("[WS] ❌ WebSocket未就绪，禁止发送数据")
                return
        
        try:
            await self.websocket.send(message)
        except Exception as e:
            logger.error(f"[WS] 发送消息失败: {e}")
            if self.on_error:
                self.on_error(e)
    
    async def send_json_message(self, message_obj: dict) -> None:
        """发送JSON消息"""
        try:
            json_string = json.dumps(message_obj)
            await self.send_message(json_string)
        except Exception as e:
            logger.error(f"[WS] JSON编码失败: {e}")
    
    async def _listen_messages(self) -> None:
        """监听消息"""
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    logger.info(f"[IN] kind=json len={len(message)} preview=\"{message[:50]}...\"")
                    await self._handle_json_message(message.encode('utf-8'))
                    
                elif isinstance(message, bytes):
                    await self._handle_binary_frame(message)
                    
        except ConnectionClosed as e:
            logger.info(f"[CLOSE] code={e.code} reason={e.reason or ''}")
            await self._handle_connection_error(e)
        except Exception as e:
            await self._handle_connection_error(e)
    
    async def _handle_binary_frame(self, data: bytes) -> None:
        """处理二进制帧 - 支持JSON探测和分片重组"""
        try:
            # 先尝试按UTF-8解析JSON
            text = data.decode('utf-8')
            self.json_buffer.extend(data)
            
            # 检查JSON完整性
            if self._is_json_complete(self.json_buffer):
                logger.info(f"[IN] kind=binary json_detected=true len={len(data)}")
                
                await self._handle_json_message(bytes(self.json_buffer))
                self.json_buffer.clear()  # 清空缓冲
            
            # 否则继续等待更多分片
            
        except UnicodeDecodeError:
            # 确实是音频数据
            if self.json_buffer:
                logger.warning("[WS] JSON缓冲区非空但收到音频数据，清空缓冲")
                self.json_buffer.clear()
            await self._handle_audio_data(data)
    
    def _is_json_complete(self, data: bytearray) -> bool:
        """检查JSON完整性"""
        try:
            text = data.decode('utf-8')
            json.loads(text)
            return True
        except:
            return False
    
    async def _handle_json_message(self, data: bytes) -> None:
        """处理JSON消息"""
        try:
            json_data = json.loads(data.decode('utf-8'))
            message_type = json_data.get("type")
            
            if message_type == "hello":
                await self._handle_hello_response(json_data)
            elif message_type == "tts":
                await self._handle_tts_message(json_data)
            elif message_type == "llm":
                await self._handle_llm_message(json_data)
            elif message_type == "mcp":
                await self._handle_mcp_message(json_data)
            else:
                logger.debug(f"[WS] 收到消息类型: {message_type}")
                
        except Exception as e:
            logger.error(f"[WS] JSON解析失败: {e}")
    
    async def _handle_hello_response(self, data: dict) -> None:
        """处理Hello响应"""
        try:
            self.session_id = data.get("session_id")
            
            if "audio_params" in data:
                audio_params = data["audio_params"]
                if "sample_rate" in audio_params:
                    self.downstream_sample_rate = audio_params["sample_rate"]
            
            logger.info(f"[HELLO][ok] session_id={self.session_id or 'nil'} down_sr={self.downstream_sample_rate}")
            
            # 握手完成，更新状态
            self.connection_state = "ready"
            DeviceStateManager().transition(DeviceState.WS_READY)
            
            # 启动心跳
            self._start_heartbeat()
            
            # 重置重连计数
            self.reconnect_attempts = 0
            
            if self.on_handshake_complete:
                self.on_handshake_complete(self.session_id)
                
        except Exception as e:
            logger.error(f"[HELLO] 解析失败: {e}")
    
    async def _handle_tts_message(self, data: dict) -> None:
        """处理TTS消息"""
        try:
            state = data.get("state")
            text = data.get("text")
            logger.debug(f"[TTS] state={state} text={text or 'nil'}")
            
            if self.on_tts_message:
                self.on_tts_message(state, text)
        except Exception as e:
            logger.error(f"[TTS] 解析失败: {e}")
    
    async def _handle_llm_message(self, data: dict) -> None:
        """处理LLM情感消息"""
        try:
            emotion = data.get("emotion")
            if emotion:
                logger.info(f"[EMO] {emotion}")
                if self.on_emotion:
                    self.on_emotion(emotion)
        except Exception as e:
            logger.error(f"[LLM] 解析失败: {e}")
    
    async def _handle_mcp_message(self, data: dict) -> None:
        """处理MCP消息"""
        try:
            logger.info("[IN] mcp.initialize protocolVersion=... capabilities=...")
            if self.on_mcp_message:
                self.on_mcp_message(data)
        except Exception as e:
            logger.error(f"[MCP] 解析失败: {e}")
    
    async def _handle_audio_data(self, data: bytes) -> None:
        """处理音频数据"""
        logger.info(f"[AUDIO] 收到音频数据: {len(data)} bytes")
        if self.on_audio_data:
            self.on_audio_data(data)
    
    async def _handle_connection_error(self, error: Exception) -> None:
        """处理连接错误"""
        logger.error(f"[WS] 连接错误: {error}")
        
        self.connection_state = "error"
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        
        if self.on_error:
            self.on_error(error)
        
        # 自动重连
        await self._schedule_reconnect()
    
    def _start_heartbeat(self) -> None:
        """启动心跳"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.debug(f"[HEARTBEAT] 启动心跳机制 ({self.heartbeat_interval}s间隔)")
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环 - 优化稳定性"""
        try:
            while self.websocket and not self.websocket.closed:
                await asyncio.sleep(self.heartbeat_interval)

                try:
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.heartbeat_ping_timeout)
                    self.heartbeat_timeout_count = 0
                    logger.debug("[HEARTBEAT] Ping成功")
                except asyncio.TimeoutError:
                    logger.warning(f"[HEARTBEAT] Ping超时 ({self.heartbeat_timeout_count + 1}/{self.max_heartbeat_timeout})")
                    self.heartbeat_timeout_count += 1

                    # 增加到5次超时才触发重连，提高容错率
                    if self.heartbeat_timeout_count >= self.max_heartbeat_timeout:
                        logger.error(f"[HEARTBEAT] 心跳超时达到上限({self.max_heartbeat_timeout}次)，触发重连")
                        await self._handle_connection_error(Exception("heartbeat_timeout"))
                        break
                except Exception as e:
                    logger.warning(f"[HEARTBEAT] Ping异常: {e}")
                    self.heartbeat_timeout_count += 1

                    if self.heartbeat_timeout_count >= self.max_heartbeat_timeout:
                        logger.error(f"[HEARTBEAT] 心跳异常达到上限，触发重连")
                        await self._handle_connection_error(e)
                        break
                        
        except asyncio.CancelledError:
            logger.debug("[HEARTBEAT] 心跳任务已取消")
        except Exception as e:
            logger.error(f"[HEARTBEAT] 心跳异常: {e}")
    
    async def _schedule_reconnect(self) -> None:
        """安排重连 - 实现真正的自动重连"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"[RECONNECT] 达到最大重试次数({self.max_reconnect_attempts})，停止重连")
            return

        if not self.last_url or not self.last_headers:
            logger.error("[RECONNECT] 缺少连接信息，无法自动重连")
            return

        delay = self.reconnect_intervals[min(self.reconnect_attempts, len(self.reconnect_intervals) - 1)]
        self.reconnect_attempts += 1

        logger.info(f"[RECONNECT] in {delay}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")

        await asyncio.sleep(delay)

        try:
            logger.info("[RECONNECT] 正在尝试重新连接...")

            # 清理旧连接
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()

            # 尝试重新连接
            await self.connect(self.last_url, self.last_headers)
            logger.info("✅ [RECONNECT] 重连成功")

        except Exception as e:
            logger.warning(f"⚠️ [RECONNECT] 重连失败: {e}")
            # 失败后继续尝试下一次重连
            await self._schedule_reconnect()
    
    def _format_headers(self, headers: Dict[str, str]) -> str:
        """格式化Headers用于日志"""
        formatted = []
        
        for key, value in headers.items():
            if key == "Authorization":
                masked_value = SensitiveDataMasker.mask(value.replace("Bearer ", ""))
                formatted.append(f"{key}=Bearer {masked_value}")
            elif key == "Client-Id":
                formatted.append(f"{key}={SensitiveDataMasker.mask_uuid(value)}")
            else:
                formatted.append(f"{key}={value}")
        
        return " ".join(formatted)

# ================================
# 主引擎类
# ================================

class XiaozhiEngine:
    """小智引擎 - 核心控制器，严格按照CLAUDE.md状态机规范"""
    
    def __init__(self, endpoint_config: Optional[EndpointConfig] = None):
        # 小智AI强制要求OPUS音频格式
        if not OPUS_AVAILABLE:
            logger.warning("❌ 小智AI强制要求OPUS音频格式")
            logger.warning("❌ 当前环境无OPUS支持，音频功能将不可用")
            logger.warning("💡 解决方案: 1. brew install opus, 2. pip install opuslib")
            
        self.endpoint_config = endpoint_config or EndpointConfig()
        self.identity_manager = IdentityManager()
        self.state_manager = DeviceStateManager()
        self.activator = Activator()
        self.websocket_client = WebSocketClient()
        self.audio_player = AudioPlayer()  # 音频播放器
        
        # 设置WebSocket客户端回调
        self.websocket_client.on_handshake_complete = self._on_websocket_handshake
        self.websocket_client.on_tts_message = self._on_tts_message
        self.websocket_client.on_emotion = self._on_emotion
        self.websocket_client.on_mcp_message = self._on_mcp_message
        self.websocket_client.on_audio_data = self._on_audio_data
        self.websocket_client.on_error = self._on_websocket_error
        
        # 外部回调
        self.on_activation_code: Optional[Callable[[str, str], None]] = None
        self.on_websocket_ready: Optional[Callable[[str, int], None]] = None
        self.on_tts: Optional[Callable[[str, Optional[str]], None]] = None
        self.on_emotion: Optional[Callable[[str], None]] = None
        self.on_audio_received: Optional[Callable[[bytes], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    async def boot(self, force_new_device: bool = False) -> None:
        """启动引擎 - 严格按照CLAUDE.md I.2规范的硬性门禁"""
        logger.info("[ENGINE] 🚀 启动小智AI引擎...")
        
        # 1. 检查设备身份
        identity = self.identity_manager.current(force_new=force_new_device)
        
        if force_new_device:
            logger.info("[EFUSE] FORCE_NEW_ID=1 triggered")
            self.activator.reset_activation()
        
        logger.info(f"[ID] deviceId={identity.device_id} clientId={SensitiveDataMasker.mask_uuid(identity.client_id)} hmacKey={SensitiveDataMasker.mask(identity.hmac_key_hex)}")
        
        # 2. 检查激活状态 - 硬性门禁
        if not identity.activated:
            logger.info("[STATE] efuse.activated=false → PendingActivation")
            self.state_manager.transition(DeviceState.PENDING_ACTIVATION)
            await self._start_activation_flow()
            return
        
        logger.info("[STATE] efuse.activated=true → Activated")
        self.state_manager.transition(DeviceState.ACTIVATED)
        await self._connect_websocket()
    
    async def _start_activation_flow(self) -> None:
        """开始激活流程"""
        logger.info("[ACT] 开始设备激活流程...")
        
        try:
            stage, code, challenge = await self.activator.ensure_activated(
                endpoint=self.endpoint_config
            )
            
            if stage == ActivationStage.NEED_CODE and code and challenge:
                logger.info("[GATE] activated=false → show code & wait user bind at xiaozhi.me")
                if self.on_activation_code:
                    self.on_activation_code(code, challenge)
            elif stage == ActivationStage.ACTIVATED:
                logger.info("[STATE] Activated → WsConnecting")
                self.state_manager.transition(DeviceState.ACTIVATED)
                await self._connect_websocket()
                
        except Exception as e:
            logger.error(f"[ACT] 激活失败: {e}")
            if self.on_error:
                self.on_error(e)
    
    async def complete_activation(self, challenge: str) -> bool:
        """用户完成官网验证码输入后调用"""
        try:
            success = await self.activator.submit_activation(
                endpoint=self.endpoint_config,
                challenge=challenge
            )
            
            if success:
                logger.info("[ACT] ✅ 激活完成，开始连接WebSocket")
                self.state_manager.transition(DeviceState.ACTIVATED)
                await self._connect_websocket()
                return True
            else:
                logger.error("[ACT] 激活失败")
                if self.on_error:
                    self.on_error(Exception("activation_failed"))
                return False
                
        except Exception as e:
            logger.error(f"[ACT] 激活失败: {e}")
            if self.on_error:
                self.on_error(e)
            return False
    
    async def _connect_websocket(self) -> None:
        """连接WebSocket - 硬性门禁检查"""
        # 硬性检查：禁止在未激活状态下连接WebSocket
        if not self.state_manager.can_connect_websocket():
            logger.error("[WS] ❌ 禁止在未激活状态下连接WebSocket！")
            if self.on_error:
                self.on_error(Exception("websocket_not_allowed"))
            return
        
        ws_url = SecureStore.get(PersistKey.WEBSOCKET_URL)
        ws_token = SecureStore.get(PersistKey.WEBSOCKET_TOKEN)
        
        if not ws_url or not ws_token:
            logger.error("[WS] 缺少WebSocket配置信息")
            if self.on_error:
                self.on_error(Exception("missing_websocket_config"))
            return
        
        logger.info("[STATE] Activated → WsConnecting")
        self.state_manager.transition(DeviceState.WS_CONNECTING)
        
        # 构建Headers
        identity = self.identity_manager.current()
        headers = self._build_websocket_headers(
            token=ws_token,
            device_id=identity.device_id,
            client_id=identity.client_id
        )
        
        # 使用WebSocket客户端连接
        await self.websocket_client.connect(url=ws_url, headers=headers)
    
    def _build_websocket_headers(self, token: str, device_id: str, client_id: str) -> Dict[str, str]:
        """构建WebSocket Headers"""
        return {
            "Authorization": f"Bearer {token if token else 'placeholder'}",
            "Protocol-Version": "1",
            "Device-Id": device_id,
            "Client-Id": client_id,
            "Origin": self.endpoint_config.origin
        }
    
    async def send_text_message(self, text: str) -> None:
        """发送文本消息"""
        if not self.state_manager.can_send_websocket_data():
            logger.error("[WS] WebSocket未就绪，无法发送文本消息")
            return
        
        # 发送唤醒词检测消息（模拟文本输入）
        wake_word_message = {
            "session_id": self.websocket_client.session_id,
            "type": "listen",
            "state": "detect",
            "text": text
        }
        
        await self.websocket_client.send_json_message(wake_word_message)
        logger.info(f"[WS] 发送文本消息: {text}")
    
    async def start_listening(self, mode: str = "auto") -> None:
        """开始音频监听"""
        if not self.state_manager.can_send_websocket_data():
            logger.error("[WS] WebSocket未就绪，无法开始监听")
            return
        
        listen_message = {
            "session_id": self.websocket_client.session_id,
            "type": "listen",
            "state": "start",
            "mode": mode
        }
        
        await self.websocket_client.send_json_message(listen_message)
        logger.info(f"[WS] 开始音频监听，模式: {mode}")
    
    async def stop_listening(self) -> None:
        """停止音频监听"""
        if not self.state_manager.can_send_websocket_data():
            return
        
        listen_message = {
            "session_id": self.websocket_client.session_id,
            "type": "listen",
            "state": "stop"
        }
        
        await self.websocket_client.send_json_message(listen_message)
        logger.info("[WS] 停止音频监听")
    
    async def disconnect(self) -> None:
        """断开WebSocket连接"""
        await self.websocket_client.disconnect()
        self.audio_player.cleanup()  # 清理音频播放器
        self.state_manager.transition(DeviceState.ACTIVATED)
    
    def reset(self) -> None:
        """重置引擎（调试用）"""
        logger.warning("[ENGINE] ⚠️ 重置引擎状态")
        self.state_manager.transition(DeviceState.UNINITIALIZED)
        self.activator.reset_activation()
    
    def get_current_state(self) -> DeviceState:
        """获取当前设备状态"""
        return self.state_manager.current_state
    
    # WebSocket客户端回调处理
    def _on_websocket_handshake(self, session_id: Optional[str]) -> None:
        """WebSocket握手完成"""
        logger.info("[STATE] WsConnecting → WsReady")
        self.state_manager.transition(DeviceState.WS_READY)
        
        # 更新音频播放器采样率
        downstream_sr = self.websocket_client.downstream_sample_rate
        if downstream_sr != self.audio_player.sample_rate:
            self.audio_player.update_sample_rate(downstream_sr)
        
        if self.on_websocket_ready:
            self.on_websocket_ready(session_id or "", downstream_sr)
    
    def _on_tts_message(self, state: str, text: Optional[str]) -> None:
        """收到TTS消息"""
        if self.on_tts:
            self.on_tts(state, text)
    
    def _on_emotion(self, emotion: str) -> None:
        """收到情感消息"""
        if self.on_emotion:
            self.on_emotion(emotion)
    
    def _on_mcp_message(self, data: Dict[str, Any]) -> None:
        """收到MCP消息"""
        # 可以在这里处理MCP协议相关逻辑
        pass
    
    def _on_audio_data(self, data: bytes) -> None:
        """收到音频数据 - 自动播放小智语音"""
        logger.info(f"[AUDIO] 收到音频数据: {len(data)} bytes")
        
        # 确保音频播放器已启动
        if not self.audio_player.is_playing:
            if self.audio_player.start_playback():
                logger.info("[AUDIO] 音频播放器已启动")
            else:
                logger.warning("[AUDIO] 无法启动音频播放器")
                
        # 实时播放音频
        asyncio.create_task(self.audio_player.play_opus_data(data))
        
        # 通知外部回调
        if self.on_audio_received:
            self.on_audio_received(data)
    
    def _on_websocket_error(self, error: Exception) -> None:
        """WebSocket错误"""
        logger.error(f"[WS] WebSocket错误: {error}")
        
        # 只在连接相关状态时才重置到激活状态
        current_state = self.state_manager.current_state
        if current_state in [DeviceState.WS_CONNECTING, DeviceState.WS_READY]:
            self.state_manager.transition(DeviceState.ACTIVATED)
        
        if self.on_error:
            self.on_error(error)

# ================================
# 演示和测试代码
# ================================

async def demo_activation_flow():
    """演示激活流程"""
    print("=" * 60)
    print("小智AI Python客户端 - 激活演示")
    print("=" * 60)
    
    # 创建引擎实例
    engine = XiaozhiEngine()
    
    # 设置回调函数
    activation_info = {}
    
    def on_activation_code(code: str, challenge: str):
        print(f"\n🔑 收到6位验证码: {code}")
        print(f"📝 请访问 https://xiaozhi.me 输入验证码完成激活")
        activation_info['challenge'] = challenge
        activation_info['code'] = code
    
    def on_websocket_ready(session_id: str, sample_rate: int):
        print(f"\n✅ WebSocket连接就绪!")
        print(f"📡 Session ID: {session_id}")
        print(f"🎵 下行采样率: {sample_rate}Hz")
    
    def on_tts(state: str, text: Optional[str]):
        print(f"🗣️  TTS: {state} - {text}")
    
    def on_emotion(emotion: str):
        print(f"😊 情感: {emotion}")
    
    def on_error(error: Exception):
        print(f"❌ 错误: {error}")
    
    # 注册回调
    engine.on_activation_code = on_activation_code
    engine.on_websocket_ready = on_websocket_ready
    engine.on_tts = on_tts
    engine.on_emotion = on_emotion
    engine.on_error = on_error
    
    # 选择是否强制生成新设备
    force_new = input("\n是否生成新设备? (y/N): ").lower().strip() == 'y'
    
    # 启动引擎
    print(f"\n🚀 启动引擎 (force_new={force_new})...")
    await engine.boot(force_new_device=force_new)
    
    # 如果需要激活，等待用户输入
    if activation_info.get('code'):
        input(f"\n⏳ 请在官网输入验证码 {activation_info['code']} 后按Enter继续...")
        
        print("🔄 开始激活轮询...")
        success = await engine.complete_activation(activation_info['challenge'])
        
        if success:
            print("✅ 激活成功!")
            # 激活成功后，等待WebSocket连接
            print("🔗 等待WebSocket连接...")
            
            # 等待WebSocket连接就绪（最多等待10秒）
            for i in range(100):  # 10秒，每100ms检查一次
                if engine.get_current_state() == DeviceState.WS_READY:
                    print("✅ WebSocket连接就绪!")
                    break
                await asyncio.sleep(0.1)
            else:
                print("⚠️ WebSocket连接超时，但可能仍在连接中...")
                
        else:
            print("❌ 激活失败!")
            return
    
    # 进入交互模式
    if engine.get_current_state() == DeviceState.WS_READY:
        print("\n🎉 恭喜！设备已完全就绪，可以开始与小智AI对话了！")
        await interactive_chat_mode(engine)
    else:
        print(f"\n⚠️ 设备状态异常: {engine.get_current_state()}")
        print("无法进入对话模式")
    
    # 断开连接
    print("\n👋 断开连接...")
    await engine.disconnect()
    
    print("\n✨ 演示完成!")

async def interactive_chat_mode(engine: XiaozhiEngine):
    """交互对话模式 - 与小智AI进行实时通信"""
    print("\n" + "=" * 60)
    print("🤖 小智AI 交互对话模式")
    print("=" * 60)
    
    print("\n📋 可用命令：")
    print("  💬 直接输入文字 - 发送文本消息给小智")
    print("  🎤 输入 'listen' - 开始语音监听模式") 
    print("  🛑 输入 'stop' - 停止当前监听")
    print("  📊 输入 'status' - 查看连接状态")
    print("  📜 输入 'history' - 查看对话历史")
    print("  🔊 输入 'audio' - 查看音频播放状态")
    print("  🔇 输入 'mute' - 静音/取消静音")  
    print("  🔄 输入 'ping' - 测试连接")
    print("  ❌ 输入 'quit' 或 Ctrl+C - 退出对话")
    
    print(f"\n✅ 当前状态: {engine.get_current_state()}")
    print(f"📡 会话ID: {engine.websocket_client.session_id or '未知'}")
    print(f"🎵 下行采样率: {engine.websocket_client.downstream_sample_rate}Hz")
    
    # 显示音频功能状态
    if AUDIO_AVAILABLE and OPUS_AVAILABLE:
        print("🔊 音频播放: ✅ 已启用 (可以听到小智语音)")
    elif AUDIO_AVAILABLE:
        print("🔊 音频播放: ⚠️ Opus解码不可用 (需要: pip install opuslib)")
    elif OPUS_AVAILABLE:
        print("🔊 音频播放: ⚠️ 音频输出不可用 (需要: pip install pyaudio)")  
    else:
        print("🔊 音频播放: ❌ 不可用 (需要: pip install pyaudio opuslib)")
        print("   💡 安装依赖后可听到小智AI的语音回复")
    
    # 消息记录
    message_history = []
    is_listening = False
    
    # 设置消息处理回调
    def on_websocket_ready(session_id: str, sample_rate: int):
        print(f"🔗 WebSocket重新连接: {session_id}")
    
    def on_tts(state: str, text: str):
        timestamp = time.strftime("%H:%M:%S")
        if state == "sentence_start" and text:
            print(f"\n[{timestamp}] 🗣️ 小智: {text}")
            message_history.append({"time": timestamp, "type": "ai_text", "content": text})
        elif state == "start":
            print(f"[{timestamp}] 🎵 小智开始说话...")
        elif state == "stop":
            print(f"[{timestamp}] 🔇 小智说话结束")
    
    def on_emotion(emotion: str):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] 😊 小智情感: {emotion}")
        message_history.append({"time": timestamp, "type": "emotion", "content": emotion})
    
    def on_audio_received(data: bytes):
        # 处理接收到的音频数据并播放
        timestamp = time.strftime("%H:%M:%S")
        
        # 显示音频接收状态
        if len(data) > 500:  # 只显示较大的音频包
            if AUDIO_AVAILABLE and OPUS_AVAILABLE:
                print(f"[{timestamp}] 🔊 播放小智语音: {len(data)} bytes", end="\r")
            else:
                print(f"[{timestamp}] 🎵 收到音频: {len(data)} bytes (无法播放)", end="\r")
            
            message_history.append({"time": timestamp, "type": "audio", "content": f"{len(data)} bytes"})
    
    def on_error(error: Exception):
        print(f"\n❌ 连接错误: {error}")
        print("尝试重新连接...")
    
    # 更新引擎回调
    engine.on_websocket_ready = on_websocket_ready
    engine.on_tts = on_tts
    engine.on_emotion = on_emotion  
    engine.on_audio_received = on_audio_received
    engine.on_error = on_error
    
    print("\n🚀 对话模式已启动！请开始与小智对话：")
    print("-" * 60)
    
    try:
        while True:
            try:
                # 获取用户输入
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: input("\n👤 你: ")
                )
                
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                    
                timestamp = time.strftime("%H:%M:%S")
                
                # 处理命令
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 退出对话模式...")
                    break
                    
                elif user_input.lower() == 'listen':
                    if not is_listening:
                        print(f"[{timestamp}] 🎤 开始语音监听...")
                        await engine.start_listening("auto")
                        is_listening = True
                        print("🔴 正在监听语音输入，说 'stop' 停止监听")
                    else:
                        print("⚠️ 已经在监听模式中")
                        
                elif user_input.lower() == 'stop':
                    if is_listening:
                        print(f"[{timestamp}] 🛑 停止语音监听")
                        await engine.stop_listening()
                        is_listening = False
                    else:
                        print("⚠️ 当前没有在监听")
                        
                elif user_input.lower() == 'status':
                    print(f"\n📊 系统状态:")
                    print(f"   设备状态: {engine.get_current_state()}")
                    print(f"   WebSocket: {engine.websocket_client.connection_state}")
                    print(f"   会话ID: {engine.websocket_client.session_id or '无'}")
                    print(f"   监听状态: {'🎤 监听中' if is_listening else '🔇 已停止'}")
                    print(f"   消息历史: {len(message_history)} 条记录")
                    
                elif user_input.lower() == 'ping':
                    print(f"[{timestamp}] 🏓 测试连接...")
                    try:
                        # 发送一个简单的测试消息
                        await engine.send_text_message("ping")
                        print("✅ 连接正常")
                    except Exception as e:
                        print(f"❌ 连接测试失败: {e}")
                        
                elif user_input.lower() == 'history':
                    print(f"\n📜 对话历史 (最近15条):")
                    if not message_history:
                        print("   暂无对话记录")
                    else:
                        recent_history = message_history[-15:]
                        for msg in recent_history:
                            if msg["type"] == "ai_text":
                                icon = "🗣️"
                            elif msg["type"] == "emotion": 
                                icon = "😊"
                            elif msg["type"] == "user_text":
                                icon = "👤"
                            elif msg["type"] == "audio":
                                icon = "🎵"
                            else:
                                icon = "📋"
                            print(f"[{msg['time']}] {icon} {msg['content']}")
                        
                        print(f"\n💬 共 {len(message_history)} 条记录")
                
                elif user_input.lower() == 'audio':
                    print(f"\n🔊 音频播放状态:")
                    audio_info = engine.audio_player.get_audio_info()
                    print(f"   播放状态: {'🔊 播放中' if audio_info['playing'] else '🔇 已停止'}")
                    print(f"   采样率: {audio_info['sample_rate']}Hz")
                    print(f"   声道数: {audio_info['channels']}")
                    print(f"   播放队列: {audio_info['queue_size']} 个音频包")
                    print(f"   Opus解码: {'✅ 可用' if audio_info['opus_available'] else '❌ 不可用'}")
                    print(f"   音频输出: {'✅ 可用' if audio_info['pyaudio_available'] else '❌ 不可用'}")
                    
                elif user_input.lower() == 'mute':
                    if engine.audio_player.is_playing:
                        engine.audio_player.stop_playback()
                        print(f"[{timestamp}] 🔇 音频播放已静音")
                    else:
                        if engine.audio_player.start_playback():
                            print(f"[{timestamp}] 🔊 音频播放已恢复")
                        else:
                            print(f"[{timestamp}] ❌ 无法启动音频播放")
                        
                else:
                    # 发送文本消息给小智
                    print(f"[{timestamp}] 💬 发送消息: {user_input}")
                    message_history.append({"time": timestamp, "type": "user_text", "content": user_input})
                    
                    try:
                        await engine.send_text_message(user_input)
                        print("✅ 消息已发送，等待小智回复...")
                        
                        # 自动开始监听小智的回复
                        if not is_listening:
                            await engine.start_listening("auto")
                            is_listening = True
                            
                    except Exception as e:
                        print(f"❌ 发送消息失败: {e}")
                
            except EOFError:
                # Ctrl+D
                print("\n👋 检测到EOF，退出对话模式...")
                break
                
            except Exception as e:
                print(f"\n❌ 处理输入时出错: {e}")
                continue
                
    except KeyboardInterrupt:
        print("\n⛔ 用户中断，退出对话模式...")
        
    finally:
        # 清理：停止监听
        if is_listening:
            try:
                await engine.stop_listening()
                print("🛑 已停止语音监听")
            except:
                pass
                
        # 显示对话统计
        if message_history:
            print(f"\n📊 对话统计:")
            user_messages = len([m for m in message_history if m["type"] == "user_text"])
            ai_messages = len([m for m in message_history if m["type"] == "ai_text"])
            emotions = len([m for m in message_history if m["type"] == "emotion"])
            
            print(f"   用户消息: {user_messages} 条")
            print(f"   AI回复: {ai_messages} 条")
            print(f"   情感变化: {emotions} 次")
            print(f"   总互动: {len(message_history)} 次")
            
        print("🔄 返回主程序...")

def demo_identity_generation():
    """演示虚拟设备生成"""
    print("=" * 60)
    print("虚拟设备身份生成演示")
    print("=" * 60)
    
    identity_manager = IdentityManager()
    
    # 生成新身份
    print("\n🔧 生成新虚拟设备身份...")
    identity = identity_manager.current(force_new=True)
    
    print(f"🆔 Device ID (虚拟MAC): {identity.device_id}")
    print(f"🔑 Client ID (UUID): {identity.client_id}")
    print(f"📄 序列号: {identity.serial}")
    print(f"🔐 HMAC密钥: {SensitiveDataMasker.mask(identity.hmac_key_hex)}")
    print(f"✅ 已激活: {identity.activated}")
    
    # 测试HMAC签名
    challenge = "test_challenge_" + str(int(time.time()))
    signature = Crypto.hmac_sha256_hex(identity.hmac_key_hex, challenge)
    
    print(f"\n🧪 HMAC签名测试:")
    print(f"   Challenge: {challenge}")
    print(f"   Signature: {SensitiveDataMasker.mask(signature)}")

async def quick_start_mode():
    """快速开始模式 - 自动处理激活和连接"""
    print("=" * 60)
    print("🚀 小智AI Python客户端 - 快速开始模式")
    print("=" * 60)
    
    # 检查现有设备
    identity_manager = IdentityManager()
    existing_identity = None
    
    try:
        if os.path.exists("xiaozhi_device.json"):
            existing_identity = identity_manager.current(force_new=False)
            if existing_identity.activated:
                print(f"✅ 发现已激活设备: {existing_identity.device_id}")
                print(f"📱 客户端ID: {SensitiveDataMasker.mask_uuid(existing_identity.client_id)}")
                
                use_existing = input("\n使用现有设备直接连接? (Y/n): ").lower().strip()
                if use_existing != 'n':
                    print("🔗 使用现有设备，直接连接WebSocket...")
                    
                    # 创建引擎并直接连接
                    engine = XiaozhiEngine()
                    
                    # 设置简单回调
                    def on_websocket_ready(session_id: str, sample_rate: int):
                        print(f"✅ WebSocket连接成功! 会话ID: {session_id}")
                    
                    def on_error(error: Exception):
                        print(f"❌ 连接错误: {error}")
                    
                    engine.on_websocket_ready = on_websocket_ready
                    engine.on_error = on_error
                    
                    # 模拟已激活状态，直接连接WebSocket
                    engine.state_manager.transition(DeviceState.ACTIVATED)
                    await engine._connect_websocket()
                    
                    # 等待连接就绪
                    for i in range(100):  # 10秒超时
                        if engine.get_current_state() == DeviceState.WS_READY:
                            await interactive_chat_mode(engine)
                            await engine.disconnect()
                            return
                        await asyncio.sleep(0.1)
                    
                    print("⚠️ WebSocket连接超时")
                    return
    except:
        pass
    
    # 没有现有设备或选择重新激活
    print("🆕 开始完整激活流程...")
    await demo_activation_flow()

if __name__ == "__main__":
    print("🤖 小智AI Python客户端")
    print("=" * 40)
    print("1. 🚀 快速开始 (推荐)")
    print("2. 📋 完整激活演示") 
    print("3. 🔧 身份生成演示")
    
    try:
        choice = input("\n请选择模式 (1/2/3): ").strip()
        
        if choice == "1":
            asyncio.run(quick_start_mode())
        elif choice == "2":
            asyncio.run(demo_activation_flow())
        elif choice == "3":
            demo_identity_generation()
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\n\n👋 再见!")
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()