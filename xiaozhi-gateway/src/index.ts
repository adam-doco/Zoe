/**
 * 小智AI WebSocket网关主入口
 * Express HTTP服务器 + WebSocket服务器
 */

import express from 'express';
import http from 'http';
import WebSocket from 'ws';
import cors from 'cors';
import dotenv from 'dotenv';
import { v4 as uuidv4 } from 'uuid';

import { 
  Config, 
  CreateSessionRequest, 
  CreateSessionResponse, 
  FrontendMessage,
  FrontendResponse,
  GatewayError,
  ErrorCodes,
  HealthStatus,
  LogContext
} from './types';
import { SessionManager } from './sessionManager';
import { AudioConverterImpl } from './audioConverter';
import { TTSManager } from './ttsManager';
import { XiaozhiClient } from './xiaozhiClient';
import { logger } from './logger';

// 加载环境变量
dotenv.config();

/**
 * 主网关类
 */
class XiaozhiGateway {
  private app: express.Application;
  private server: http.Server;
  private wss: WebSocket.Server;
  private sessionManager: SessionManager;
  private audioConverter: AudioConverterImpl;
  private ttsManager: TTSManager;
  private config: Config;
  private startTime: Date;

  constructor() {
    this.startTime = new Date();
    this.config = this.loadConfig();
    this.app = express();
    this.server = http.createServer(this.app);
    this.wss = new WebSocket.Server({ noServer: true });

    // 初始化组件
    this.sessionManager = new SessionManager(this.config);
    this.audioConverter = new AudioConverterImpl(this.config);
    this.ttsManager = new TTSManager(this.config);

    // 设置Express中间件
    this.setupMiddleware();
    
    // 设置路由
    this.setupRoutes();
    
    // 设置WebSocket处理
    this.setupWebSocket();
    
    // 设置事件监听器
    this.setupEventListeners();

    logger.info('Xiaozhi Gateway initialized', {
      port: this.config.server.port,
      nodeEnv: this.config.server.nodeEnv
    });
  }

  /**
   * 加载配置
   */
  private loadConfig(): Config {
    return {
      xiaozhi: {
        serverUrl: process.env.XIAOZHI_SERVER_URL || 'wss://api.tenclass.net/xiaozhi/v1/',
        accessToken: process.env.XIAOZHI_ACCESS_TOKEN || '',
        deviceId: process.env.XIAOZHI_DEVICE_ID || 'gateway-001',
        clientId: process.env.XIAOZHI_CLIENT_ID || 'nodejs-gateway'
      },
      server: {
        port: parseInt(process.env.PORT || '3000'),
        nodeEnv: process.env.NODE_ENV || 'development'
      },
      tts: {
        storage: (process.env.TTS_STORAGE as 'memory' | 'file') || 'memory',
        maxAge: parseInt(process.env.TTS_MAX_AGE || '300000'),
        baseUrl: process.env.TTS_BASE_URL || `http://localhost:${process.env.PORT || '3000'}`
      },
      log: {
        level: process.env.LOG_LEVEL || 'info',
        file: process.env.LOG_FILE
      },
      audio: {
        sampleRate: parseInt(process.env.OPUS_SAMPLE_RATE || '16000'),
        channels: parseInt(process.env.OPUS_CHANNELS || '1'),
        frameSize: parseInt(process.env.OPUS_FRAME_SIZE || '960')
      },
      session: {
        timeout: parseInt(process.env.SESSION_TIMEOUT || '600000'),
        maxSessions: parseInt(process.env.MAX_SESSIONS || '1000')
      }
    };
  }

  /**
   * 设置Express中间件
   */
  private setupMiddleware(): void {
    this.app.use(cors());
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.raw({ type: 'audio/*', limit: '10mb' }));
    
    // 请求日志
    this.app.use((req, res, next) => {
      const logContext: LogContext = {
        method: req.method,
        url: req.url,
        userAgent: req.get('User-Agent'),
        ip: req.ip
      };
      logger.info(`${req.method} ${req.url}`, logContext);
      next();
    });

    // 错误处理中间件
    this.app.use((error: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
      if (error instanceof GatewayError) {
        logger.error('Gateway error', { error: error.message, code: error.code });
        res.status(error.statusCode).json({
          error: error.message,
          code: error.code
        });
      } else {
        logger.error('Unexpected error', { error });
        res.status(500).json({
          error: 'Internal server error',
          code: 'INTERNAL_ERROR'
        });
      }
    });
  }

  /**
   * 设置HTTP路由
   */
  private setupRoutes(): void {
    // 健康检查
    this.app.get('/healthz', (req, res) => {
      const uptime = Date.now() - this.startTime.getTime();
      const sessionStats = this.sessionManager.getStats();
      const ttsStats = this.ttsManager.getStats();

      const health: HealthStatus = {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        services: {
          xiaozhi: 'unknown', // 这里可以添加更复杂的健康检查逻辑
          sessions: sessionStats,
          tts: ttsStats
        },
        uptime,
        version: '1.0.0'
      };

      res.json(health);
    });

    // 创建会话 - 简化版，无需授权
    this.app.post('/session', async (req, res, next) => {
      try {
        const { userId }: CreateSessionRequest = req.body;
        
        if (!userId) {
          throw new GatewayError(
            'userId is required',
            ErrorCodes.INVALID_MESSAGE_FORMAT,
            400
          );
        }

        // 检查是否配置了访问令牌
        if (!this.config.xiaozhi.accessToken) {
          return res.status(500).json({
            error: 'CONFIGURATION_ERROR',
            message: '小智访问令牌未配置，请检查环境变量 XIAOZHI_ACCESS_TOKEN'
          });
        }

        const session = await this.sessionManager.createSession(userId);
        const wsUrl = `ws://localhost:${this.config.server.port}/ws/${session.sessionId}`;

        const response: CreateSessionResponse = {
          sessionId: session.sessionId,
          wsUrl
        };

        logger.info('Session created', {
          sessionId: session.sessionId,
          userId,
          hasAccessToken: !!this.config.xiaozhi.accessToken
        });

        res.json(response);

      } catch (error) {
        next(error);
      }
    });

    // TTS文件服务
    this.app.get('/tts/:id', async (req, res, next) => {
      try {
        const { id } = req.params;
        const ttsFile = await this.ttsManager.getTTS(id);

        if (!ttsFile) {
          return res.status(404).json({
            error: 'TTS file not found',
            code: ErrorCodes.SESSION_NOT_FOUND
          });
        }

        res.set({
          'Content-Type': ttsFile.mimeType,
          'Content-Length': ttsFile.data.length.toString(),
          'Cache-Control': 'public, max-age=300' // 5分钟缓存
        });

        res.send(ttsFile.data);

        logger.debug('TTS file served', {
          id,
          sessionId: ttsFile.sessionId,
          size: ttsFile.data.length
        });

      } catch (error) {
        next(error);
      }
    });

    // 获取会话信息（调试用）
    this.app.get('/sessions', (req, res) => {
      if (this.config.server.nodeEnv !== 'development') {
        return res.status(404).json({ error: 'Not found' });
      }

      const sessions = this.sessionManager.getAllSessions();
      res.json({
        sessions: sessions.map(s => ({
          sessionId: s.sessionId,
          userId: s.userId,
          createdAt: s.createdAt,
          lastActiveAt: s.lastActiveAt,
          isConnected: s.isConnected
        }))
      });
    });
  }

  /**
   * 设置WebSocket处理
   */
  private setupWebSocket(): void {
    // HTTP升级处理
    this.server.on('upgrade', (request, socket, head) => {
      const pathname = new URL(request.url!, `http://${request.headers.host}`).pathname;
      
      if (pathname.startsWith('/ws/')) {
        const sessionId = pathname.substring(4); // 移除 '/ws/' 前缀
        
        // 验证会话
        const session = this.sessionManager.getSession(sessionId);
        if (!session) {
          logger.warn('WebSocket upgrade rejected: session not found', { sessionId });
          socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
          socket.destroy();
          return;
        }

        this.wss.handleUpgrade(request, socket, head, (ws) => {
          this.handleWebSocketConnection(ws, sessionId);
        });
      } else {
        socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
        socket.destroy();
      }
    });
  }

  /**
   * 处理WebSocket连接
   */
  private async handleWebSocketConnection(ws: WebSocket, sessionId: string): Promise<void> {
    const logContext: LogContext = { sessionId, action: 'websocket_connection' };
    
    try {
      // 连接前端WebSocket
      await this.sessionManager.connectFrontend(sessionId, ws);

      // 创建小智客户端
      const xiaozhiClient = new XiaozhiClient(this.config, sessionId);
      
      // 设置小智客户端事件监听器
      this.setupXiaozhiClientEvents(xiaozhiClient, sessionId, ws);
      
      // 连接到小智AI
      await xiaozhiClient.connect();
      await this.sessionManager.connectXiaozhi(sessionId, xiaozhiClient as any);

      // 设置前端WebSocket消息处理
      ws.on('message', async (data: Buffer) => {
        await this.handleFrontendMessage(data, sessionId, xiaozhiClient);
      });

      ws.on('close', () => {
        logger.info('Frontend WebSocket closed', logContext);
        xiaozhiClient.destroy();
      });

      ws.on('error', (error) => {
        logger.error('Frontend WebSocket error', { ...logContext, error });
        xiaozhiClient.destroy();
      });

      logger.info('WebSocket connection established', logContext);

    } catch (error) {
      logger.error('Failed to establish WebSocket connection', { ...logContext, error });
      ws.close(1011, 'Server error');
    }
  }

  /**
   * 设置小智客户端事件监听器
   */
  private setupXiaozhiClientEvents(xiaozhiClient: XiaozhiClient, sessionId: string, frontendWs: WebSocket): void {
    // STT文本消息
    xiaozhiClient.on('stt', (message) => {
      this.sendToFrontend(frontendWs, {
        type: 'stt',
        sessionId,
        data: {
          text: message.text,
          final: message.final
        }
      });
    });

    // LLM响应消息
    xiaozhiClient.on('llm', (message) => {
      this.sendToFrontend(frontendWs, {
        type: 'llm',
        sessionId,
        data: {
          text: message.text,
          emotion: message.emotion
        }
      });
    });

    // TTS状态消息
    xiaozhiClient.on('tts', (message) => {
      if (message.state === 'start') {
        this.sendToFrontend(frontendWs, {
          type: 'tts_start',
          sessionId,
          data: {
            text: message.text,
            ttsId: message.tts_id
          }
        });
      } else if (message.state === 'stop') {
        this.sendToFrontend(frontendWs, {
          type: 'tts_end',
          sessionId,
          data: {
            ttsId: message.tts_id
          }
        });
      }
    });

    // TTS音频数据
    xiaozhiClient.on('tts_audio', async (sessionId, audioData) => {
      try {
        // 存储TTS音频
        const ttsId = await this.ttsManager.storeTTS(audioData, 'audio/opus', sessionId);
        const ttsUrl = this.ttsManager.getTTSUrl(ttsId);

        // 发送TTS URL给前端
        this.sendToFrontend(frontendWs, {
          type: 'tts_url',
          sessionId,
          data: {
            ttsId,
            url: ttsUrl
          }
        });

        logger.info('TTS audio stored and URL sent', {
          sessionId,
          ttsId,
          size: audioData.length
        });

      } catch (error) {
        logger.error('Failed to store TTS audio', { sessionId, error });
        this.sendToFrontend(frontendWs, {
          type: 'error',
          sessionId,
          data: {
            message: 'Failed to process TTS audio'
          }
        });
      }
    });

    // 连接错误
    xiaozhiClient.on('error', (error) => {
      logger.error('Xiaozhi client error', { sessionId, error });
      this.sendToFrontend(frontendWs, {
        type: 'error',
        sessionId,
        data: {
          message: error.message
        }
      });
    });
  }

  /**
   * 处理前端消息
   */
  private async handleFrontendMessage(data: Buffer, sessionId: string, xiaozhiClient: XiaozhiClient): Promise<void> {
    const logContext: LogContext = { sessionId, action: 'handle_frontend_message' };

    try {
      // 尝试解析JSON消息
      const message: FrontendMessage = JSON.parse(data.toString());
      
      logger.debug('Received frontend message', { ...logContext, type: message.type });

      switch (message.type) {
        case 'interrupt':
          await xiaozhiClient.sendAbort('user_interrupt');
          logger.info('Interrupt sent to Xiaozhi', logContext);
          break;

        case 'ping':
          // 发送pong响应
          if (xiaozhiClient.isConnected()) {
            this.sendToFrontend(xiaozhiClient as any, {
              type: 'pong',
              sessionId,
              data: {}
            });
          }
          break;

        default:
          logger.warn('Unknown frontend message type', { ...logContext, type: message.type });
      }

    } catch (parseError) {
      // 如果不是JSON，假设是PCM音频数据
      await this.handleAudioData(data, sessionId, xiaozhiClient);
    }
  }

  /**
   * 处理音频数据
   */
  private async handleAudioData(pcmData: Buffer, sessionId: string, xiaozhiClient: XiaozhiClient): Promise<void> {
    const logContext: LogContext = { sessionId, action: 'handle_audio_data' };

    try {
      // 将PCM转换为小智协议的音频帧
      const audioFrames = this.audioConverter.processContinuousAudio(pcmData, sessionId);

      // 发送所有音频帧到小智
      for (const frame of audioFrames) {
        await xiaozhiClient.sendAudio(frame);
      }

      logger.debug('Audio data processed and sent', {
        ...logContext,
        inputSize: pcmData.length,
        frameCount: audioFrames.length
      });

    } catch (error) {
      logger.error('Failed to process audio data', { ...logContext, error });
      
      // 发送错误消息给前端
      const session = this.sessionManager.getSession(sessionId);
      if (session && session.frontendWs) {
        this.sendToFrontend(session.frontendWs, {
          type: 'error',
          sessionId,
          data: {
            message: 'Audio processing failed'
          }
        });
      }
    }
  }

  /**
   * 向前端发送消息
   */
  private sendToFrontend(ws: WebSocket, message: FrontendResponse): void {
    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(message));
        logger.debug('Sent message to frontend', {
          sessionId: message.sessionId,
          type: message.type
        });
      } catch (error) {
        logger.error('Failed to send message to frontend', {
          sessionId: message.sessionId,
          error
        });
      }
    }
  }

  /**
   * 设置事件监听器
   */
  private setupEventListeners(): void {
    // 会话事件
    this.sessionManager.on('session:created', (session) => {
      logger.info('Session created event', { sessionId: session.sessionId });
    });

    this.sessionManager.on('session:destroyed', (sessionId) => {
      logger.info('Session destroyed event', { sessionId });
    });

    // TTS事件
    this.ttsManager.on('tts:stored', (file) => {
      logger.debug('TTS file stored event', { 
        id: file.id, 
        sessionId: file.sessionId 
      });
    });

    // 进程事件
    process.on('SIGTERM', this.shutdown.bind(this));
    process.on('SIGINT', this.shutdown.bind(this));
    process.on('uncaughtException', (error) => {
      logger.error('Uncaught exception', { error });
      this.shutdown();
    });
    process.on('unhandledRejection', (reason, promise) => {
      logger.error('Unhandled rejection', { reason, promise });
    });
  }

  /**
   * 启动服务器
   */
  async start(): Promise<void> {
    return new Promise((resolve) => {
      this.server.listen(this.config.server.port, () => {
        logger.info(`Xiaozhi Gateway started on port ${this.config.server.port}`, {
          nodeEnv: this.config.server.nodeEnv,
          ttsStorage: this.config.tts.storage,
          hasAccessToken: !!this.config.xiaozhi.accessToken
        });
        resolve();
      });
    });
  }

  /**
   * 优雅关闭
   */
  private async shutdown(): Promise<void> {
    logger.info('Shutting down Xiaozhi Gateway...');

    try {
      // 关闭HTTP服务器
      await new Promise<void>((resolve) => {
        this.server.close(() => resolve());
      });

      // 关闭WebSocket服务器
      this.wss.close();

      // 销毁组件
      this.sessionManager.destroy();
      this.audioConverter.destroy();
      this.ttsManager.destroy();

      logger.info('Xiaozhi Gateway shutdown complete');
      process.exit(0);

    } catch (error) {
      logger.error('Error during shutdown', { error });
      process.exit(1);
    }
  }
}

// 启动网关
if (require.main === module) {
  const gateway = new XiaozhiGateway();
  gateway.start().catch((error) => {
    logger.error('Failed to start gateway', { error });
    process.exit(1);
  });
}

export { XiaozhiGateway };