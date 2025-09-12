/**
 * 小智AI WebSocket客户端封装
 * 负责与小智AI服务的WebSocket通信
 */

import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { 
  Config, 
  XiaozhiHelloMessage, 
  XiaozhiTextMessage, 
  XiaozhiTtsMessage, 
  XiaozhiAbortMessage,
  GatewayError,
  ErrorCodes,
  LogContext
} from './types';
import { logger } from './logger';
import { OTAClient } from './otaClient';

export interface XiaozhiClientEvents {
  'connected': () => void;
  'disconnected': (code: number, reason: string) => void;
  'error': (error: Error) => void;
  'stt': (message: XiaozhiTextMessage) => void;
  'llm': (message: XiaozhiTextMessage) => void;
  'tts': (message: XiaozhiTtsMessage) => void;
  'tts_audio': (sessionId: string, audioData: Buffer) => void;
  'session_ready': (sessionId: string) => void;
}

export class XiaozhiClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 5000; // 5秒
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isDestroyed = false;
  private otaClient: OTAClient;
  private accessToken: string | null = null;

  constructor(
    private config: Config,
    sessionId: string
  ) {
    super();
    this.sessionId = sessionId;
    this.otaClient = new OTAClient(config);
  }

  /**
   * 连接到小智AI服务
   */
  async connect(): Promise<void> {
    if (this.isDestroyed) {
      throw new GatewayError(
        'Client has been destroyed',
        ErrorCodes.XIAOZHI_CONNECTION_FAILED,
        400
      );
    }

    const logContext: LogContext = { sessionId: this.sessionId, action: 'xiaozhi_connect' };

    try {
      logger.info('Connecting to Xiaozhi AI', logContext);

      // 从OTA获取真实的访问令牌
      if (!this.accessToken) {
        logger.info('Fetching access token from OTA server', logContext);
        try {
          this.accessToken = await this.otaClient.getWebSocketToken();
        } catch (error) {
          logger.error('Failed to get access token from OTA', { ...logContext, error });
          throw new GatewayError(
            'Failed to get access token from OTA server',
            ErrorCodes.XIAOZHI_CONNECTION_FAILED,
            500
          );
        }
      }

      // 创建WebSocket连接 - 采用PC版方式
      this.ws = new WebSocket(this.config.xiaozhi.serverUrl, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Protocol-Version': '1',
          'Device-Id': this.config.xiaozhi.deviceId,
          'Client-Id': this.config.xiaozhi.clientId,
          'User-Agent': 'xiaozhi-gateway/1.0.0'
        },
        timeout: 10000 // 10秒连接超时
      });

      // 设置事件监听器
      this.setupEventListeners();

      // 等待连接建立
      await new Promise<void>((resolve, reject) => {
        if (!this.ws) {
          reject(new Error('WebSocket is null'));
          return;
        }

        const onOpen = () => {
          if (this.ws) {
            this.ws.off('error', onError);
            resolve();
          }
        };

        const onError = (error: Error) => {
          if (this.ws) {
            this.ws.off('open', onOpen);
            reject(error);
          }
        };

        this.ws.once('open', onOpen);
        this.ws.once('error', onError);
      });

      // 发送握手消息
      await this.sendHello();

      // 重置重连计数
      this.reconnectAttempts = 0;

      // 启动心跳
      this.startHeartbeat();

      logger.info('Connected to Xiaozhi AI successfully', logContext);
      this.emit('connected');

    } catch (error) {
      const errorMsg = `Failed to connect to Xiaozhi AI: ${error instanceof Error ? error.message : error}`;
      logger.error(errorMsg, { ...logContext, error });
      
      this.cleanup();
      
      throw new GatewayError(
        errorMsg,
        ErrorCodes.XIAOZHI_CONNECTION_FAILED,
        500
      );
    }
  }

  /**
   * 设置WebSocket事件监听器
   */
  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.on('open', () => {
      logger.debug('Xiaozhi WebSocket opened', { sessionId: this.sessionId });
    });

    this.ws.on('message', (data: Buffer) => {
      this.handleMessage(data);
    });

    this.ws.on('close', (code: number, reason: Buffer) => {
      const reasonStr = reason.toString();
      logger.warn('Xiaozhi WebSocket closed', {
        sessionId: this.sessionId,
        code,
        reason: reasonStr
      });

      this.cleanup();
      this.emit('disconnected', code, reasonStr);

      // 尝试重连（除非是正常关闭或客户端已销毁）
      if (code !== 1000 && !this.isDestroyed) {
        this.scheduleReconnect();
      }
    });

    this.ws.on('error', (error: Error) => {
      logger.error('Xiaozhi WebSocket error', {
        sessionId: this.sessionId,
        error: error.message
      });
      this.emit('error', error);
    });

    this.ws.on('ping', (data: Buffer) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.pong(data);
      }
    });
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: Buffer): void {
    try {
      // 尝试解析为JSON消息
      const message = JSON.parse(data.toString());
      
      logger.debug('Received message from Xiaozhi', {
        sessionId: this.sessionId,
        type: message.type
      });

      switch (message.type) {
        case 'stt':
          this.emit('stt', message as XiaozhiTextMessage);
          break;

        case 'llm':
          this.emit('llm', message as XiaozhiTextMessage);
          break;

        case 'tts':
          this.emit('tts', message as XiaozhiTtsMessage);
          break;

        case 'session_ready':
          logger.info('Xiaozhi session ready', { sessionId: this.sessionId });
          this.emit('session_ready', this.sessionId);
          break;

        case 'error':
          logger.error('Xiaozhi error message', {
            sessionId: this.sessionId,
            error: message
          });
          this.emit('error', new Error(`Xiaozhi error: ${message.message || 'Unknown error'}`));
          break;

        default:
          logger.debug('Unknown message type from Xiaozhi', {
            sessionId: this.sessionId,
            type: message.type,
            message
          });
      }

    } catch (parseError) {
      // 如果不是JSON，可能是二进制音频数据
      this.handleBinaryMessage(data);
    }
  }

  /**
   * 处理二进制消息（TTS音频）
   */
  private handleBinaryMessage(data: Buffer): void {
    try {
      // 小智的TTS音频数据可能有特定的二进制格式
      // 这里简化处理，假设直接是音频数据
      logger.debug('Received binary audio data from Xiaozhi', {
        sessionId: this.sessionId,
        size: data.length
      });

      this.emit('tts_audio', this.sessionId, data);

    } catch (error) {
      logger.error('Failed to handle binary message', {
        sessionId: this.sessionId,
        error,
        dataSize: data.length
      });
    }
  }

  /**
   * 发送握手消息
   */
  private async sendHello(): Promise<void> {
    const helloMessage = {
      type: 'hello',
      version: 1,
      features: {
        mcp: true,
      },
      transport: 'websocket',
      audio_params: {
        format: 'opus',
        sample_rate: 16000,
        channels: 1,
        frame_duration: 60,
      },
    };

    await this.sendMessage(helloMessage);
    logger.debug('Sent hello message to Xiaozhi', { sessionId: this.sessionId });
  }

  /**
   * 发送JSON消息
   */
  async sendMessage(message: any): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new GatewayError(
        'WebSocket is not connected',
        ErrorCodes.XIAOZHI_CONNECTION_FAILED,
        503
      );
    }

    try {
      const messageStr = JSON.stringify(message);
      this.ws.send(messageStr);
      
      logger.debug('Sent message to Xiaozhi', {
        sessionId: this.sessionId,
        type: message.type
      });

    } catch (error) {
      logger.error('Failed to send message to Xiaozhi', {
        sessionId: this.sessionId,
        error,
        messageType: message.type
      });
      throw error;
    }
  }

  /**
   * 发送二进制音频数据
   */
  async sendAudio(audioData: Buffer): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new GatewayError(
        'WebSocket is not connected',
        ErrorCodes.XIAOZHI_CONNECTION_FAILED,
        503
      );
    }

    try {
      this.ws.send(audioData);
      
      logger.debug('Sent audio data to Xiaozhi', {
        sessionId: this.sessionId,
        size: audioData.length
      });

    } catch (error) {
      logger.error('Failed to send audio to Xiaozhi', {
        sessionId: this.sessionId,
        error,
        dataSize: audioData.length
      });
      throw error;
    }
  }

  /**
   * 发送中断消息
   */
  async sendAbort(reason: string = 'user_interrupt'): Promise<void> {
    const abortMessage: XiaozhiAbortMessage = {
      type: 'abort',
      session_id: this.sessionId,
      reason
    };

    await this.sendMessage(abortMessage);
    logger.info('Sent abort message to Xiaozhi', { 
      sessionId: this.sessionId, 
      reason 
    });
  }

  /**
   * 启动心跳
   */
  private startHeartbeat(): void {
    // 清除现有心跳
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }

    // 每30秒发送一次ping
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.ping();
      }
    }, 30000);
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(): void {
    if (this.isDestroyed || this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectInterval * this.reconnectAttempts;

    logger.info(`Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`, {
      sessionId: this.sessionId
    });

    this.reconnectTimer = setTimeout(() => {
      if (!this.isDestroyed) {
        this.connect().catch(error => {
          logger.error('Reconnect attempt failed', {
            sessionId: this.sessionId,
            attempt: this.reconnectAttempts,
            error
          });
        });
      }
    }, delay);
  }

  /**
   * 清理资源
   */
  private cleanup(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  /**
   * 检查连接状态
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * 获取连接状态
   */
  getConnectionState(): string {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
        return 'closing';
      case WebSocket.CLOSED:
        return 'closed';
      default:
        return 'unknown';
    }
  }

  /**
   * 销毁客户端
   */
  destroy(): void {
    this.isDestroyed = true;
    this.cleanup();
    this.removeAllListeners();
    
    logger.info('Xiaozhi client destroyed', { sessionId: this.sessionId });
  }
}