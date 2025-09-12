/**
 * 类型定义文件
 * 定义所有接口、类型和消息格式
 */

import { WebSocket } from 'ws';

// ==================== 基础类型 ====================

export interface Config {
  xiaozhi: {
    serverUrl: string;
    accessToken: string;
    deviceId: string;
    clientId: string;
    otaUrl?: string;
  };
  server: {
    port: number;
    nodeEnv: string;
  };
  tts: {
    storage: 'memory' | 'file';
    maxAge: number;
    baseUrl: string;
  };
  log: {
    level: string;
    file?: string;
  };
  audio: {
    sampleRate: number;
    channels: number;
    frameSize: number;
  };
  session: {
    timeout: number;
    maxSessions: number;
  };
}

// ==================== 会话相关 ====================

export interface Session {
  sessionId: string;
  userId: string;
  createdAt: Date;
  lastActiveAt: Date;
  xiaozhiWs?: WebSocket;
  frontendWs?: WebSocket;
  isConnected: boolean;
  audioBuffer: Buffer[];
}

export interface CreateSessionRequest {
  userId: string;
  capabilities?: string[];
}

export interface CreateSessionResponse {
  sessionId: string;
  wsUrl: string;
}

// ==================== WebSocket消息类型 ====================

// 前端发送的消息
export interface FrontendMessage {
  type: 'audio' | 'interrupt' | 'ping';
  sessionId?: string;
  data?: any;
}

// 发送给前端的消息
export interface FrontendResponse {
  type: 'stt' | 'llm' | 'tts_start' | 'tts_url' | 'tts_end' | 'error' | 'pong';
  sessionId: string;
  data?: any;
}

// ==================== 小智AI消息格式 ====================

// 小智握手消息
export interface XiaozhiHelloMessage {
  type: 'hello';
  session_id: string;
  device_id?: string;
  capabilities?: string[];
  version?: string;
}

// 小智文本消息
export interface XiaozhiTextMessage {
  type: 'stt' | 'llm';
  session_id: string;
  text: string;
  emotion?: string;
  final?: boolean;
}

// 小智TTS消息
export interface XiaozhiTtsMessage {
  type: 'tts';
  session_id: string;
  state: 'start' | 'stop' | 'sentence_start' | 'sentence_end';
  text?: string;
  tts_id?: string;
}

// 小智中断消息
export interface XiaozhiAbortMessage {
  type: 'abort';
  session_id: string;
  reason: string;
}

// 小智音频数据（二进制）
export interface XiaozhiAudioFrame {
  version: number; // 协议版本 v1/v2/v3
  session_id: string;
  frame_id: number;
  is_final: boolean;
  data: Buffer; // Opus音频数据
}

// ==================== TTS相关 ====================

export interface TTSFile {
  id: string;
  sessionId: string;
  data: Buffer;
  mimeType: string;
  createdAt: Date;
  expiresAt: Date;
}

export interface TTSStorage {
  store(id: string, data: Buffer, mimeType: string, sessionId: string): Promise<void>;
  get(id: string): Promise<TTSFile | null>;
  delete(id: string): Promise<void>;
  cleanup(): Promise<void>;
  getUrl(id: string): string;
  getStats(): { count: number; memoryUsage?: string; diskUsage?: string };
  destroy(): void;
  
  // EventEmitter methods
  on(event: string, listener: (...args: any[]) => void): this;
  emit(event: string, ...args: any[]): boolean;
  removeAllListeners(event?: string): this;
}

// ==================== 音频转码相关 ====================

export interface AudioConverter {
  pcmToOpus(pcmData: Buffer): Buffer;
  opusToPcm(opusData: Buffer): Buffer;
}

export interface OpusEncoderConfig {
  sampleRate: number;
  channels: number;
  frameSize: number;
  bitrate?: number;
}

// ==================== 错误类型 ====================

export class GatewayError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 500,
    public sessionId?: string
  ) {
    super(message);
    this.name = 'GatewayError';
  }
}

export enum ErrorCodes {
  SESSION_NOT_FOUND = 'SESSION_NOT_FOUND',
  SESSION_EXPIRED = 'SESSION_EXPIRED',
  XIAOZHI_CONNECTION_FAILED = 'XIAOZHI_CONNECTION_FAILED',
  AUDIO_ENCODE_FAILED = 'AUDIO_ENCODE_FAILED',
  TTS_STORAGE_FAILED = 'TTS_STORAGE_FAILED',
  INVALID_MESSAGE_FORMAT = 'INVALID_MESSAGE_FORMAT',
  MAX_SESSIONS_EXCEEDED = 'MAX_SESSIONS_EXCEEDED'
}

// ==================== 事件类型 ====================

export interface SessionEvents {
  'session:created': (session: Session) => void;
  'session:destroyed': (sessionId: string) => void;
  'session:connected': (sessionId: string) => void;
  'session:disconnected': (sessionId: string) => void;
  'audio:received': (sessionId: string, data: Buffer) => void;
  'text:received': (sessionId: string, text: string, type: 'stt' | 'llm') => void;
  'tts:received': (sessionId: string, ttsId: string, data: Buffer) => void;
  'error:occurred': (error: GatewayError) => void;
}

// ==================== 健康检查 ====================

export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
  services: {
    xiaozhi: 'connected' | 'disconnected' | 'unknown';
    sessions: {
      active: number;
      total: number;
    };
    tts: {
      stored: number;
      memoryUsage?: string;
    };
  };
  uptime: number;
  version: string;
}

// ==================== 日志相关 ====================

export interface LogContext {
  sessionId?: string;
  userId?: string;
  action?: string;
  error?: Error;
  [key: string]: any;
}