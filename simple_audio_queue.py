#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单音频队列 - 替换复杂的JSON队列系统
使用临时文件 + 信号机制处理音频数据
"""

import os
import tempfile
import time
import threading
from typing import Optional

class SimpleAudioQueue:
    """简单可靠的音频队列实现"""

    def __init__(self):
        # 创建临时目录
        self.audio_dir = os.path.join(tempfile.gettempdir(), "xiaozhi_audio")
        os.makedirs(self.audio_dir, exist_ok=True)

        # 跨进程音频文件计数器文件
        self.counter_file = os.path.join(self.audio_dir, "counter.txt")
        self.counter_lock = threading.Lock()

        # 状态文件
        self.status_file = os.path.join(self.audio_dir, "status.txt")
        self.listening_file = os.path.join(self.audio_dir, "listening.signal")

        # 初始化计数器文件
        self._init_counter_file()

        print(f"🎵 [AUDIO_QUEUE] 初始化完成: {self.audio_dir}")

    def _init_counter_file(self):
        """初始化跨进程计数器文件"""
        try:
            if not os.path.exists(self.counter_file):
                with open(self.counter_file, 'w') as f:
                    f.write("0")
                print(f"✅ [AUDIO_QUEUE] 计数器文件已创建: {self.counter_file}")
        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 初始化计数器失败: {e}")
            # 强制重新创建
            try:
                os.makedirs(os.path.dirname(self.counter_file), exist_ok=True)
                with open(self.counter_file, 'w') as f:
                    f.write("0")
                print(f"🔧 [AUDIO_QUEUE] 强制重建计数器文件成功")
            except Exception as e2:
                print(f"💥 [AUDIO_QUEUE] 无法创建计数器文件: {e2}")

    def _get_next_counter(self):
        """获取下一个跨进程安全的计数器值"""
        import fcntl
        try:
            # 使用文件锁确保跨进程原子操作
            with open(self.counter_file, 'r+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取独占锁
                try:
                    f.seek(0)
                    current_count = int(f.read().strip() or "0")
                    next_count = current_count + 1

                    f.seek(0)
                    f.truncate()
                    f.write(str(next_count))
                    f.flush()

                    return next_count
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 获取计数器失败: {e}")
            # 回退到基于时间戳的ID
            return int(time.time() * 1000000) % 1000000

    def start_listening(self):
        """开始监听音频"""
        try:
            with open(self.listening_file, 'w') as f:
                f.write(f"start:{time.time()}")
            print(f"🎤 [AUDIO_QUEUE] 开始监听信号已写入")
            return True
        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 开始监听失败: {e}")
            return False

    def stop_listening(self):
        """停止监听音频 - 标记为处理中状态"""
        try:
            # 不立即删除监听文件，而是修改其内容为"processing"状态
            # 这样robust_message_handler仍然会处理音频数据
            if os.path.exists(self.listening_file):
                with open(self.listening_file, 'w') as f:
                    f.write(f"processing:{time.time()}")
            print(f"🔄 [AUDIO_QUEUE] 监听状态改为处理中")
            return True
        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 停止监听失败: {e}")
            return False

    def add_audio_chunk(self, pcm_data: bytes) -> bool:
        """添加音频块（跨进程安全）"""
        try:
            # 获取跨进程安全的唯一ID
            chunk_id = self._get_next_counter()

            # 写入音频文件
            audio_file = os.path.join(self.audio_dir, f"chunk_{chunk_id:06d}.pcm")
            with open(audio_file, 'wb') as f:
                f.write(pcm_data)

            # 使用文件锁安全地写入状态文件
            status_info = f"chunk:{chunk_id}:{len(pcm_data)}:{time.time()}\n"
            import fcntl
            try:
                with open(self.status_file, 'a') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取独占锁
                    try:
                        f.write(status_info)
                        f.flush()
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
            except Exception as e:
                print(f"⚠️ [AUDIO_QUEUE] 状态文件写入警告: {e}")
                # 即使状态文件写入失败，音频文件已保存，仍然返回成功

            print(f"🎵 [AUDIO_QUEUE] 音频块已保存: chunk_{chunk_id:06d}.pcm ({len(pcm_data)} bytes)")
            return True

        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 音频块保存失败: {e}")
            return False

    def is_listening(self) -> bool:
        """检查是否正在监听或处理中"""
        if not os.path.exists(self.listening_file):
            return False

        # 读取文件内容判断状态
        try:
            with open(self.listening_file, 'r') as f:
                content = f.read().strip()
            # 无论是 "start:时间戳" 还是 "processing:时间戳" 都认为在监听状态
            return content.startswith(('start:', 'processing:'))
        except Exception:
            return False

    def get_new_chunks(self) -> list:
        """获取新的音频块列表（跨进程安全）"""
        try:
            chunks = []
            import fcntl
            import time

            # 首先尝试从status文件读取
            if os.path.exists(self.status_file):
                # 使用文件锁安全读取状态文件
                try:
                    with open(self.status_file, 'r') as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 获取共享锁
                        try:
                            lines = f.readlines()
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁

                    # 如果status文件有内容，使用status文件的记录
                    if lines:
                        for line in lines:
                            line = line.strip()
                            if line.startswith('chunk:'):
                                parts = line.split(':')
                                if len(parts) >= 4:
                                    try:
                                        chunk_id = int(parts[1])
                                        size = int(parts[2])
                                        timestamp = float(parts[3])

                                        audio_file = os.path.join(self.audio_dir, f"chunk_{chunk_id:06d}.pcm")
                                        if os.path.exists(audio_file):
                                            chunks.append({
                                                'id': chunk_id,
                                                'file': audio_file,
                                                'size': size,
                                                'timestamp': timestamp
                                            })
                                    except (ValueError, IndexError) as e:
                                        print(f"⚠️ [AUDIO_QUEUE] 解析音频块信息失败: {line} - {e}")
                                        continue
                        return chunks
                except Exception as e:
                    print(f"⚠️ [AUDIO_QUEUE] 状态文件读取警告: {e}")

            # 如果status文件不存在或为空，直接扫描音频目录中的PCM文件
            print(f"📁 [AUDIO_QUEUE] 状态文件为空，直接扫描音频文件...")
            try:
                for filename in os.listdir(self.audio_dir):
                    if filename.startswith('chunk_') and filename.endswith('.pcm'):
                        try:
                            # 提取chunk ID
                            chunk_id_str = filename[6:12]  # chunk_000XXX.pcm
                            chunk_id = int(chunk_id_str)

                            audio_file = os.path.join(self.audio_dir, filename)
                            file_stat = os.stat(audio_file)
                            size = file_stat.st_size
                            timestamp = file_stat.st_mtime

                            chunks.append({
                                'id': chunk_id,
                                'file': audio_file,
                                'size': size,
                                'timestamp': timestamp
                            })
                        except (ValueError, IndexError, OSError) as e:
                            print(f"⚠️ [AUDIO_QUEUE] 解析音频文件失败: {filename} - {e}")
                            continue

                # 按chunk_id排序
                chunks.sort(key=lambda x: x['id'])
                print(f"📁 [AUDIO_QUEUE] 从文件系统发现 {len(chunks)} 个音频块")
            except Exception as e:
                print(f"❌ [AUDIO_QUEUE] 扫描音频目录失败: {e}")

            return chunks

        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 获取音频块失败: {e}")
            return []

    def clear_processed_chunks(self, chunk_ids: list):
        """清理已处理的音频块（跨进程安全）"""
        try:
            # 删除音频文件
            deleted_count = 0
            for chunk_id in chunk_ids:
                audio_file = os.path.join(self.audio_dir, f"chunk_{chunk_id:06d}.pcm")
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                    deleted_count += 1

            # 安全地清空状态文件
            import fcntl
            try:
                if os.path.exists(self.status_file):
                    with open(self.status_file, 'w') as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取独占锁
                        try:
                            f.truncate()  # 清空文件
                            f.flush()
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
            except Exception as e:
                print(f"⚠️ [AUDIO_QUEUE] 清空状态文件警告: {e}")

            # 音频处理完成后，真正删除监听信号文件
            try:
                if os.path.exists(self.listening_file):
                    os.remove(self.listening_file)
                    print(f"🛑 [AUDIO_QUEUE] 监听信号已删除（处理完成）")
            except Exception as e:
                print(f"⚠️ [AUDIO_QUEUE] 删除监听信号警告: {e}")

            print(f"🧹 [AUDIO_QUEUE] 已清理 {deleted_count} 个音频块")
            return True

        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 清理失败: {e}")
            return False

    def clear_all(self):
        """清空所有数据"""
        try:
            # 删除所有文件
            for filename in os.listdir(self.audio_dir):
                file_path = os.path.join(self.audio_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            print(f"🧹 [AUDIO_QUEUE] 已清空所有音频数据")
            return True

        except Exception as e:
            print(f"❌ [AUDIO_QUEUE] 清空失败: {e}")
            return False

# 全局音频队列实例
audio_queue = SimpleAudioQueue()

def get_audio_queue():
    """获取音频队列实例"""
    return audio_queue

if __name__ == "__main__":
    print("🎵 简单音频队列模块")
    queue = get_audio_queue()
    print(f"音频目录: {queue.audio_dir}")
    print(f"监听状态: {queue.is_listening()}")