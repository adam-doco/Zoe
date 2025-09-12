/**
 * OTA客户端 - 从小智AI服务获取配置和token
 */

import { logger } from './logger';
import { Config } from './types';
import { DeviceActivator, ActivationResponse, DeviceFingerprint } from './deviceActivator';
import * as fs from 'fs';
import * as path from 'path';

export class OTAClient {
  private config: Config;
  private macAddr: string;
  private clientId: string;
  private fingerprint: DeviceFingerprint | null = null;
  private activator: DeviceActivator | null = null;

  constructor(config: Config) {
    this.config = config;
    // 使用配置中的设备ID作为MAC地址
    this.macAddr = config.xiaozhi.deviceId;
    this.clientId = config.xiaozhi.clientId;
    // 加载设备指纹
    this.loadDeviceFingerprint();
  }

  /**
   * 加载设备指纹文件
   */
  private loadDeviceFingerprint(): void {
    try {
      // 从PC客户端的路径读取efuse.json
      const efusePath = '/Users/good/Desktop/Zoe/xiaozhi/pc_xiaozhi/third_party/py-xiaozhi/config/efuse.json';
      
      if (fs.existsSync(efusePath)) {
        const efuseData = fs.readFileSync(efusePath, 'utf-8');
        this.fingerprint = JSON.parse(efuseData) as DeviceFingerprint;
        this.activator = new DeviceActivator(this.config, this.fingerprint);
        logger.info('Device fingerprint loaded', {
          serialNumber: this.fingerprint.serial_number,
          macAddress: this.fingerprint.mac_address,
          activationStatus: this.fingerprint.activation_status,
        });
      } else {
        logger.warn('Device fingerprint file not found', { path: efusePath });
      }
    } catch (error) {
      logger.error('Failed to load device fingerprint', { error });
    }
  }

  /**
   * 构建OTA请求的headers
   */
  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Device-Id': this.macAddr,
      'Client-Id': this.clientId,
      'Content-Type': 'application/json',
      'User-Agent': 'xiaozhi-gateway/1.0.0',
      'Accept-Language': 'zh-CN',
    };

    // 添加Activation-Version头部用于v2协议
    headers['Activation-Version'] = '1.0.0';
    
    return headers;
  }

  /**
   * 构建OTA请求的payload
   */
  private buildPayload(): any {
    // 使用HMAC密钥作为elf_sha256，如果没有则使用unknown
    const elf_sha256 = this.fingerprint?.hmac_key || 'unknown';
    
    return {
      application: {
        version: '1.0.0',
        elf_sha256: elf_sha256,
      },
      board: {
        type: 'xiaozhi-gateway',
        name: 'xiaozhi-gateway',
        ip: '127.0.0.1', // 本地IP
        mac: this.macAddr,
      },
    };
  }

  /**
   * 获取OTA配置
   */
  async getOTAConfig(): Promise<ActivationResponse> {
    const otaUrl = 'https://api.tenclass.net/xiaozhi/ota/';
    const headers = this.buildHeaders();
    const payload = this.buildPayload();

    logger.info('Fetching OTA configuration', {
      url: otaUrl,
      deviceId: this.macAddr,
      clientId: this.clientId,
    });

    try {
      const response = await fetch(otaUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`OTA server error: HTTP ${response.status}`);
      }

      const data = await response.json() as ActivationResponse;
      logger.info('OTA configuration received', {
        hasWebsocket: !!data.websocket,
        hasMqtt: !!data.mqtt,
        hasActivation: !!data.activation,
      });

      return data;
    } catch (error) {
      logger.error('Failed to fetch OTA configuration', { error });
      throw new Error(`OTA request failed: ${error instanceof Error ? error.message : error}`);
    }
  }

  /**
   * 获取WebSocket访问令牌 - 自动处理激活流程
   */
  async getWebSocketToken(): Promise<string> {
    try {
      const otaData = await this.getOTAConfig();

      // 检查是否需要激活
      if (otaData.activation) {
        logger.info('Device activation required', {
          message: otaData.activation.message,
          code: otaData.activation.code,
        });

        // 检查是否有激活器
        if (!this.activator) {
          throw new Error('Device fingerprint not loaded, cannot perform activation');
        }

        // 执行激活流程
        const activationSuccess = await this.activator.handleActivationFlow(otaData.activation);
        
        if (!activationSuccess) {
          throw new Error('Device activation failed');
        }

        // 激活成功后，重新获取OTA配置以获取真实token
        logger.info('Activation successful, fetching updated configuration...');
        const updatedOtaData = await this.getOTAConfig();
        
        if (!updatedOtaData.websocket) {
          throw new Error('No WebSocket configuration after activation');
        }

        const token = updatedOtaData.websocket.token;
        if (!token || token === 'test-token') {
          throw new Error('Still receiving test-token after activation');
        }

        logger.info('Real WebSocket token obtained after activation', {
          tokenLength: token.length,
          tokenPrefix: token.substring(0, 8) + '...',
        });

        return token;
      }

      // 不需要激活，直接返回token
      if (!otaData.websocket) {
        throw new Error('No WebSocket configuration in OTA response');
      }

      const token = otaData.websocket.token;
      if (!token) {
        throw new Error('No WebSocket token in OTA response');
      }

      // 检查是否为test-token
      if (token === 'test-token') {
        logger.warn('Received test-token, device may not be properly activated');
      }

      logger.info('WebSocket token obtained from OTA', {
        tokenLength: token.length,
        tokenPrefix: token.substring(0, 8) + '...',
        isTestToken: token === 'test-token',
      });

      return token;
    } catch (error) {
      logger.error('Failed to get WebSocket token', { error });
      throw error;
    }
  }
}