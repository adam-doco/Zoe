/**
 * TTS管理器
 * 负责TTS音频文件的存储、管理和URL服务
 */

import { v4 as uuidv4 } from 'uuid';
import fs from 'fs/promises';
import path from 'path';
import { EventEmitter } from 'events';
import { TTSStorage, TTSFile, Config, GatewayError, ErrorCodes } from './types';
import { logger } from './logger';

/**
 * 内存存储实现
 */
class MemoryTTSStorage extends EventEmitter implements TTSStorage {
  private files = new Map<string, TTSFile>();
  private cleanupInterval: NodeJS.Timeout;

  constructor(private config: Config) {
    super();
    
    // 启动清理定时器，每分钟清理过期文件
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, 60000);
  }

  async store(id: string, data: Buffer, mimeType: string, sessionId: string): Promise<void> {
    const now = new Date();
    const expiresAt = new Date(now.getTime() + this.config.tts.maxAge);

    const file: TTSFile = {
      id,
      sessionId,
      data: Buffer.from(data), // 创建副本
      mimeType,
      createdAt: now,
      expiresAt
    };

    this.files.set(id, file);

    logger.debug('TTS file stored in memory', {
      id,
      sessionId,
      size: data.length,
      mimeType,
      expiresAt: expiresAt.toISOString()
    });

    this.emit('file:stored', file);
  }

  async get(id: string): Promise<TTSFile | null> {
    const file = this.files.get(id);
    if (!file) {
      return null;
    }

    // 检查是否过期
    if (file.expiresAt < new Date()) {
      await this.delete(id);
      return null;
    }

    return file;
  }

  async delete(id: string): Promise<void> {
    const file = this.files.get(id);
    if (file) {
      this.files.delete(id);
      logger.debug('TTS file deleted from memory', { id, sessionId: file.sessionId });
      this.emit('file:deleted', id);
    }
  }

  async cleanup(): Promise<void> {
    const now = new Date();
    const expiredIds: string[] = [];

    for (const [id, file] of this.files) {
      if (file.expiresAt < now) {
        expiredIds.push(id);
      }
    }

    if (expiredIds.length > 0) {
      logger.info(`Cleaning up ${expiredIds.length} expired TTS files from memory`);
      for (const id of expiredIds) {
        await this.delete(id);
      }
    }
  }

  getUrl(id: string): string {
    return `${this.config.tts.baseUrl}/tts/${id}`;
  }

  getStats(): { count: number; memoryUsage: string } {
    const totalSize = Array.from(this.files.values())
      .reduce((sum, file) => sum + file.data.length, 0);

    return {
      count: this.files.size,
      memoryUsage: `${(totalSize / 1024 / 1024).toFixed(2)}MB`
    };
  }

  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }
    this.files.clear();
    this.removeAllListeners();
  }
}

/**
 * 文件系统存储实现
 */
class FileTTSStorage extends EventEmitter implements TTSStorage {
  private readonly storageDir = 'tts-storage';
  private files = new Map<string, Omit<TTSFile, 'data'>>(); // 元数据缓存
  private cleanupInterval: NodeJS.Timeout;

  constructor(private config: Config) {
    super();
    this.initStorageDir();
    
    // 启动清理定时器
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, 60000);
  }

  private async initStorageDir(): Promise<void> {
    try {
      await fs.access(this.storageDir);
    } catch {
      await fs.mkdir(this.storageDir, { recursive: true });
      logger.info(`Created TTS storage directory: ${this.storageDir}`);
    }
  }

  async store(id: string, data: Buffer, mimeType: string, sessionId: string): Promise<void> {
    const now = new Date();
    const expiresAt = new Date(now.getTime() + this.config.tts.maxAge);
    const filePath = this.getFilePath(id);

    try {
      // 保存音频文件
      await fs.writeFile(filePath, data);

      // 保存元数据
      const metadata = {
        id,
        sessionId,
        mimeType,
        createdAt: now,
        expiresAt,
        filePath
      };

      const metadataPath = this.getMetadataPath(id);
      await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2));

      // 缓存元数据
      this.files.set(id, {
        id,
        sessionId,
        mimeType,
        createdAt: now,
        expiresAt
      });

      logger.debug('TTS file stored to disk', {
        id,
        sessionId,
        size: data.length,
        mimeType,
        filePath,
        expiresAt: expiresAt.toISOString()
      });

      this.emit('file:stored', { id, sessionId, mimeType, createdAt: now, expiresAt, data });

    } catch (error) {
      logger.error('Failed to store TTS file to disk', { id, sessionId, error });
      throw new GatewayError(
        'TTS file storage failed',
        ErrorCodes.TTS_STORAGE_FAILED,
        500
      );
    }
  }

  async get(id: string): Promise<TTSFile | null> {
    try {
      let metadata = this.files.get(id);

      // 如果缓存中没有，尝试从磁盘加载
      if (!metadata) {
        const metadataPath = this.getMetadataPath(id);
        try {
          const metadataContent = await fs.readFile(metadataPath, 'utf8');
          const parsedMetadata = JSON.parse(metadataContent);
          metadata = {
            id: parsedMetadata.id,
            sessionId: parsedMetadata.sessionId,
            mimeType: parsedMetadata.mimeType,
            createdAt: new Date(parsedMetadata.createdAt),
            expiresAt: new Date(parsedMetadata.expiresAt)
          };
          this.files.set(id, metadata);
        } catch {
          return null; // 元数据文件不存在或损坏
        }
      }

      // 检查是否过期
      if (metadata.expiresAt < new Date()) {
        await this.delete(id);
        return null;
      }

      // 读取音频数据
      const filePath = this.getFilePath(id);
      const data = await fs.readFile(filePath);

      return {
        ...metadata,
        data
      };

    } catch (error) {
      logger.error('Failed to get TTS file from disk', { id, error });
      return null;
    }
  }

  async delete(id: string): Promise<void> {
    try {
      const filePath = this.getFilePath(id);
      const metadataPath = this.getMetadataPath(id);

      // 删除文件（忽略错误，可能文件已经不存在）
      await Promise.allSettled([
        fs.unlink(filePath),
        fs.unlink(metadataPath)
      ]);

      // 从缓存中删除
      const file = this.files.get(id);
      this.files.delete(id);

      logger.debug('TTS file deleted from disk', { 
        id, 
        sessionId: file?.sessionId,
        filePath 
      });

      this.emit('file:deleted', id);

    } catch (error) {
      logger.error('Failed to delete TTS file from disk', { id, error });
    }
  }

  async cleanup(): Promise<void> {
    const now = new Date();
    const expiredIds: string[] = [];

    // 检查缓存中的过期文件
    for (const [id, file] of this.files) {
      if (file.expiresAt < now) {
        expiredIds.push(id);
      }
    }

    // 也检查磁盘上可能遗漏的文件
    try {
      const files = await fs.readdir(this.storageDir);
      const metadataFiles = files.filter(f => f.endsWith('.json'));

      for (const metadataFile of metadataFiles) {
        const id = metadataFile.replace('.json', '');
        if (expiredIds.includes(id)) continue; // 已经在待删除列表中

        try {
          const metadataPath = path.join(this.storageDir, metadataFile);
          const content = await fs.readFile(metadataPath, 'utf8');
          const metadata = JSON.parse(content);
          
          if (new Date(metadata.expiresAt) < now) {
            expiredIds.push(id);
          }
        } catch (error) {
          // 元数据文件损坏，也加入删除列表
          expiredIds.push(id);
        }
      }
    } catch (error) {
      logger.error('Failed to scan TTS storage directory', { error });
    }

    if (expiredIds.length > 0) {
      logger.info(`Cleaning up ${expiredIds.length} expired TTS files from disk`);
      for (const id of expiredIds) {
        await this.delete(id);
      }
    }
  }

  getUrl(id: string): string {
    return `${this.config.tts.baseUrl}/tts/${id}`;
  }

  private getFilePath(id: string): string {
    return path.join(this.storageDir, `${id}.audio`);
  }

  private getMetadataPath(id: string): string {
    return path.join(this.storageDir, `${id}.json`);
  }

  getStats(): { count: number; memoryUsage?: string; diskUsage?: string } {
    return {
      count: this.files.size
      // 磁盘使用量计算较复杂，这里省略
    };
  }

  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }
    this.files.clear();
    this.removeAllListeners();
  }
}

/**
 * TTS管理器主类
 */
export class TTSManager extends EventEmitter {
  private storage: TTSStorage;

  constructor(private config: Config) {
    super();

    // 根据配置选择存储方式
    if (config.tts.storage === 'file') {
      this.storage = new FileTTSStorage(config);
    } else {
      this.storage = new MemoryTTSStorage(config);
    }

    // 转发存储事件
    this.storage.on('file:stored', (file) => this.emit('tts:stored', file));
    this.storage.on('file:deleted', (id) => this.emit('tts:deleted', id));

    logger.info('TTS Manager initialized', { 
      storageType: config.tts.storage,
      maxAge: config.tts.maxAge 
    });
  }

  /**
   * 存储TTS音频文件
   */
  async storeTTS(data: Buffer, mimeType: string, sessionId: string): Promise<string> {
    const id = uuidv4();
    
    try {
      await this.storage.store(id, data, mimeType, sessionId);
      
      logger.info('TTS file stored', { 
        id, 
        sessionId, 
        size: data.length, 
        mimeType 
      });

      return id;

    } catch (error) {
      logger.error('Failed to store TTS file', { sessionId, error });
      throw new GatewayError(
        'TTS storage failed',
        ErrorCodes.TTS_STORAGE_FAILED,
        500
      );
    }
  }

  /**
   * 获取TTS文件
   */
  async getTTS(id: string): Promise<TTSFile | null> {
    return await this.storage.get(id);
  }

  /**
   * 获取TTS文件URL
   */
  getTTSUrl(id: string): string {
    return this.storage.getUrl(id);
  }

  /**
   * 删除TTS文件
   */
  async deleteTTS(id: string): Promise<void> {
    await this.storage.delete(id);
  }

  /**
   * 获取统计信息
   */
  getStats(): { stored: number; memoryUsage?: string; diskUsage?: string } {
    const stats = this.storage.getStats();
    return {
      stored: stats.count,
      memoryUsage: 'memoryUsage' in stats ? stats.memoryUsage : undefined,
      diskUsage: 'diskUsage' in stats ? stats.diskUsage : undefined
    };
  }

  /**
   * 手动清理过期文件
   */
  async cleanup(): Promise<void> {
    if ('cleanup' in this.storage) {
      await this.storage.cleanup();
    }
  }

  /**
   * 销毁管理器
   */
  destroy(): void {
    if ('destroy' in this.storage) {
      this.storage.destroy();
    }
    this.removeAllListeners();
    logger.info('TTS Manager destroyed');
  }
}