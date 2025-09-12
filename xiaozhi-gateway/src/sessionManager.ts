/**
 * 会话管理器
 * 负责管理用户会话、WebSocket连接和状态维护
 */

import { v4 as uuidv4 } from 'uuid';
import { EventEmitter } from 'events';
import { WebSocket } from 'ws';
import { Session, Config, GatewayError, ErrorCodes, LogContext } from './types';
import { logger } from './logger';

export class SessionManager extends EventEmitter {
  private sessions = new Map<string, Session>();
  private userSessions = new Map<string, string>(); // userId -> sessionId
  private cleanupInterval: NodeJS.Timeout;

  constructor(private config: Config) {
    super();
    
    // 启动清理定时器，每分钟清理过期会话
    this.cleanupInterval = setInterval(() => {
      this.cleanupExpiredSessions();
    }, 60000);
  }

  /**
   * 创建新会话
   */
  async createSession(userId: string): Promise<Session> {
    // 检查是否超出最大会话数
    if (this.sessions.size >= this.config.session.maxSessions) {
      throw new GatewayError(
        'Maximum number of sessions exceeded',
        ErrorCodes.MAX_SESSIONS_EXCEEDED,
        429
      );
    }

    // 如果用户已有活跃会话，先销毁旧会话
    const existingSessionId = this.userSessions.get(userId);
    if (existingSessionId) {
      await this.destroySession(existingSessionId);
    }

    const sessionId = uuidv4();
    const now = new Date();

    const session: Session = {
      sessionId,
      userId,
      createdAt: now,
      lastActiveAt: now,
      isConnected: false,
      audioBuffer: []
    };

    this.sessions.set(sessionId, session);
    this.userSessions.set(userId, sessionId);

    const logContext: LogContext = { sessionId, userId, action: 'session_created' };
    logger.info('Session created', logContext);

    this.emit('session:created', session);
    return session;
  }

  /**
   * 获取会话
   */
  getSession(sessionId: string): Session | null {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return null;
    }

    // 检查是否过期
    if (this.isSessionExpired(session)) {
      this.destroySession(sessionId);
      return null;
    }

    // 更新活跃时间
    session.lastActiveAt = new Date();
    return session;
  }

  /**
   * 连接前端WebSocket
   */
  async connectFrontend(sessionId: string, ws: WebSocket): Promise<void> {
    const session = this.getSession(sessionId);
    if (!session) {
      throw new GatewayError(
        'Session not found',
        ErrorCodes.SESSION_NOT_FOUND,
        404,
        sessionId
      );
    }

    // 如果已有前端连接，关闭旧连接
    if (session.frontendWs && session.frontendWs.readyState === WebSocket.OPEN) {
      session.frontendWs.close();
    }

    session.frontendWs = ws;
    session.isConnected = true;
    session.lastActiveAt = new Date();

    // 监听WebSocket关闭事件
    ws.on('close', () => {
      this.handleFrontendDisconnect(sessionId);
    });

    ws.on('error', (error) => {
      const logContext: LogContext = { 
        sessionId, 
        userId: session.userId, 
        action: 'frontend_ws_error',
        error 
      };
      logger.error('Frontend WebSocket error', logContext);
    });

    const logContext: LogContext = { 
      sessionId, 
      userId: session.userId, 
      action: 'frontend_connected' 
    };
    logger.info('Frontend WebSocket connected', logContext);

    this.emit('session:connected', sessionId);
  }

  /**
   * 连接小智WebSocket
   */
  async connectXiaozhi(sessionId: string, ws: WebSocket): Promise<void> {
    const session = this.getSession(sessionId);
    if (!session) {
      throw new GatewayError(
        'Session not found',
        ErrorCodes.SESSION_NOT_FOUND,
        404,
        sessionId
      );
    }

    // 如果已有小智连接，关闭旧连接
    if (session.xiaozhiWs && session.xiaozhiWs.readyState === WebSocket.OPEN) {
      session.xiaozhiWs.close();
    }

    session.xiaozhiWs = ws;
    session.lastActiveAt = new Date();

    // 监听WebSocket事件
    ws.on('close', () => {
      this.handleXiaozhiDisconnect(sessionId);
    });

    ws.on('error', (error) => {
      const logContext: LogContext = { 
        sessionId, 
        userId: session.userId, 
        action: 'xiaozhi_ws_error',
        error 
      };
      logger.error('Xiaozhi WebSocket error', logContext);
    });

    const logContext: LogContext = { 
      sessionId, 
      userId: session.userId, 
      action: 'xiaozhi_connected' 
    };
    logger.info('Xiaozhi WebSocket connected', logContext);
  }

  /**
   * 处理前端断开连接
   */
  private handleFrontendDisconnect(sessionId: string): void {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.isConnected = false;
      session.frontendWs = undefined;

      const logContext: LogContext = { 
        sessionId, 
        userId: session.userId, 
        action: 'frontend_disconnected' 
      };
      logger.info('Frontend WebSocket disconnected', logContext);

      this.emit('session:disconnected', sessionId);

      // 延迟销毁会话（给重连一些时间）
      setTimeout(() => {
        if (!session.isConnected) {
          this.destroySession(sessionId);
        }
      }, 30000); // 30秒后销毁
    }
  }

  /**
   * 处理小智断开连接
   */
  private handleXiaozhiDisconnect(sessionId: string): void {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.xiaozhiWs = undefined;

      const logContext: LogContext = { 
        sessionId, 
        userId: session.userId, 
        action: 'xiaozhi_disconnected' 
      };
      logger.info('Xiaozhi WebSocket disconnected', logContext);
    }
  }

  /**
   * 销毁会话
   */
  async destroySession(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return;
    }

    // 关闭WebSocket连接
    if (session.frontendWs && session.frontendWs.readyState === WebSocket.OPEN) {
      session.frontendWs.close();
    }
    if (session.xiaozhiWs && session.xiaozhiWs.readyState === WebSocket.OPEN) {
      session.xiaozhiWs.close();
    }

    // 清理映射
    this.sessions.delete(sessionId);
    this.userSessions.delete(session.userId);

    const logContext: LogContext = { 
      sessionId, 
      userId: session.userId, 
      action: 'session_destroyed' 
    };
    logger.info('Session destroyed', logContext);

    this.emit('session:destroyed', sessionId);
  }

  /**
   * 检查会话是否过期
   */
  private isSessionExpired(session: Session): boolean {
    const now = Date.now();
    const lastActive = session.lastActiveAt.getTime();
    return (now - lastActive) > this.config.session.timeout;
  }

  /**
   * 清理过期会话
   */
  private async cleanupExpiredSessions(): Promise<void> {
    const expiredSessions: string[] = [];

    for (const [sessionId, session] of this.sessions) {
      if (this.isSessionExpired(session)) {
        expiredSessions.push(sessionId);
      }
    }

    if (expiredSessions.length > 0) {
      logger.info(`Cleaning up ${expiredSessions.length} expired sessions`);
      
      for (const sessionId of expiredSessions) {
        await this.destroySession(sessionId);
      }
    }
  }

  /**
   * 获取会话统计信息
   */
  getStats(): { active: number; total: number } {
    const activeSessions = Array.from(this.sessions.values())
      .filter(session => session.isConnected).length;

    return {
      active: activeSessions,
      total: this.sessions.size
    };
  }

  /**
   * 获取所有会话信息（调试用）
   */
  getAllSessions(): Session[] {
    return Array.from(this.sessions.values());
  }

  /**
   * 清理资源
   */
  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    // 销毁所有会话
    const sessionIds = Array.from(this.sessions.keys());
    sessionIds.forEach(sessionId => {
      this.destroySession(sessionId);
    });

    this.removeAllListeners();
  }
}