/**
 * 音频转码器
 * 负责PCM到Opus的音频格式转换
 */

import { OpusEncoder } from '@discordjs/opus';
import { Config, AudioConverter, OpusEncoderConfig, GatewayError, ErrorCodes } from './types';
import { logger } from './logger';

export class AudioConverterImpl implements AudioConverter {
  private encoder: OpusEncoder;
  private config: OpusEncoderConfig;

  constructor(config: Config) {
    this.config = {
      sampleRate: config.audio.sampleRate,
      channels: config.audio.channels,
      frameSize: config.audio.frameSize,
      bitrate: 64000 // 64kbps，适合语音
    };

    try {
      this.encoder = new OpusEncoder(this.config.sampleRate, this.config.channels);
      logger.info('Opus encoder initialized', {
        sampleRate: this.config.sampleRate,
        channels: this.config.channels,
        frameSize: this.config.frameSize,
        bitrate: this.config.bitrate
      });
    } catch (error) {
      logger.error('Failed to initialize Opus encoder', { error });
      throw new GatewayError(
        'Failed to initialize audio encoder',
        ErrorCodes.AUDIO_ENCODE_FAILED,
        500
      );
    }
  }

  /**
   * 将PCM音频转换为Opus格式
   * @param pcmData PCM音频数据 (16-bit, 16kHz, mono)
   * @returns Opus编码的音频数据
   */
  pcmToOpus(pcmData: Buffer): Buffer {
    try {
      // 验证PCM数据长度
      const expectedFrameSize = this.config.frameSize * this.config.channels * 2; // 16-bit = 2 bytes
      
      if (pcmData.length !== expectedFrameSize) {
        logger.warn('PCM frame size mismatch', {
          expected: expectedFrameSize,
          actual: pcmData.length
        });
        
        // 如果数据不足，用0填充
        if (pcmData.length < expectedFrameSize) {
          const paddedBuffer = Buffer.alloc(expectedFrameSize);
          pcmData.copy(paddedBuffer);
          pcmData = paddedBuffer;
        } else {
          // 如果数据过多，截断
          pcmData = pcmData.subarray(0, expectedFrameSize);
        }
      }

      // 执行Opus编码
      const opusData = this.encoder.encode(pcmData);
      
      logger.debug('Audio encoded', {
        inputSize: pcmData.length,
        outputSize: opusData.length,
        compressionRatio: (pcmData.length / opusData.length).toFixed(2)
      });

      return opusData;

    } catch (error) {
      logger.error('PCM to Opus encoding failed', { 
        error,
        inputSize: pcmData.length 
      });
      throw new GatewayError(
        'Audio encoding failed',
        ErrorCodes.AUDIO_ENCODE_FAILED,
        500
      );
    }
  }

  /**
   * 将Opus音频转换为PCM格式（如果需要的话）
   * 注：当前主要用于PCM到Opus的单向转换
   */
  opusToPcm(opusData: Buffer): Buffer {
    try {
      // 注意：@discordjs/opus 主要用于编码，解码功能可能有限
      // 如果需要解码，可能需要额外的库如 node-opus
      throw new Error('Opus to PCM decoding not implemented in current version');
    } catch (error) {
      logger.error('Opus to PCM decoding failed', { error });
      throw new GatewayError(
        'Audio decoding failed',
        ErrorCodes.AUDIO_ENCODE_FAILED,
        500
      );
    }
  }

  /**
   * 创建小智AI WebSocket协议的音频帧
   * @param sessionId 会话ID
   * @param opusData Opus编码的音频数据
   * @param frameId 帧ID
   * @param isFinal 是否为最后一帧
   * @returns 符合小智协议的二进制数据
   */
  createXiaozhiAudioFrame(
    sessionId: string, 
    opusData: Buffer, 
    frameId: number, 
    isFinal: boolean = false
  ): Buffer {
    try {
      // 小智WebSocket音频协议 v3 格式
      // [版本(1byte)][会话ID长度(1byte)][会话ID][帧ID(4bytes)][是否最后帧(1byte)][音频数据长度(4bytes)][音频数据]
      
      const sessionIdBuffer = Buffer.from(sessionId, 'utf8');
      const sessionIdLength = sessionIdBuffer.length;
      
      // 计算总长度
      const totalLength = 1 + 1 + sessionIdLength + 4 + 1 + 4 + opusData.length;
      const frame = Buffer.alloc(totalLength);
      
      let offset = 0;
      
      // 版本号 (v3)
      frame.writeUInt8(3, offset);
      offset += 1;
      
      // 会话ID长度
      frame.writeUInt8(sessionIdLength, offset);
      offset += 1;
      
      // 会话ID
      sessionIdBuffer.copy(frame, offset);
      offset += sessionIdLength;
      
      // 帧ID (Big Endian)
      frame.writeUInt32BE(frameId, offset);
      offset += 4;
      
      // 是否最后帧
      frame.writeUInt8(isFinal ? 1 : 0, offset);
      offset += 1;
      
      // 音频数据长度 (Big Endian)
      frame.writeUInt32BE(opusData.length, offset);
      offset += 4;
      
      // 音频数据
      opusData.copy(frame, offset);
      
      logger.debug('Xiaozhi audio frame created', {
        sessionId,
        frameId,
        isFinal,
        opusDataSize: opusData.length,
        totalFrameSize: frame.length
      });
      
      return frame;

    } catch (error) {
      logger.error('Failed to create Xiaozhi audio frame', { 
        error,
        sessionId,
        frameId 
      });
      throw new GatewayError(
        'Failed to create audio frame',
        ErrorCodes.AUDIO_ENCODE_FAILED,
        500
      );
    }
  }

  /**
   * 批量处理音频数据
   * 将连续的PCM数据分割成固定大小的帧并编码
   */
  processContinuousAudio(
    pcmData: Buffer, 
    sessionId: string,
    startFrameId: number = 0
  ): Buffer[] {
    const frameSize = this.config.frameSize * this.config.channels * 2; // 16-bit PCM
    const frames: Buffer[] = [];
    let frameId = startFrameId;

    try {
      // 按帧大小分割音频数据
      for (let offset = 0; offset < pcmData.length; offset += frameSize) {
        const isLastFrame = (offset + frameSize >= pcmData.length);
        let frameData = pcmData.subarray(offset, offset + frameSize);

        // 如果是最后一帧且数据不足，用静音填充
        if (frameData.length < frameSize) {
          const paddedFrame = Buffer.alloc(frameSize);
          frameData.copy(paddedFrame);
          frameData = paddedFrame;
        }

        // PCM转Opus
        const opusData = this.pcmToOpus(frameData);
        
        // 创建小智协议帧
        const xiaozhiFrame = this.createXiaozhiAudioFrame(
          sessionId, 
          opusData, 
          frameId++, 
          isLastFrame
        );
        
        frames.push(xiaozhiFrame);
      }

      logger.debug('Continuous audio processed', {
        inputSize: pcmData.length,
        frameCount: frames.length,
        sessionId
      });

      return frames;

    } catch (error) {
      logger.error('Failed to process continuous audio', { 
        error,
        sessionId,
        inputSize: pcmData.length 
      });
      throw new GatewayError(
        'Audio processing failed',
        ErrorCodes.AUDIO_ENCODE_FAILED,
        500
      );
    }
  }

  /**
   * 获取音频编码器信息
   */
  getEncoderInfo(): OpusEncoderConfig {
    return { ...this.config };
  }

  /**
   * 清理资源
   */
  destroy(): void {
    try {
      if (this.encoder) {
        // Opus编码器通常不需要显式清理，但保留接口以备将来使用
        logger.info('Audio encoder destroyed');
      }
    } catch (error) {
      logger.error('Error destroying audio encoder', { error });
    }
  }
}