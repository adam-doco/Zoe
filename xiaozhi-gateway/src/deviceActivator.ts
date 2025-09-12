import crypto from 'crypto';
import { Config } from './types';

export interface ActivationResponse {
  activation?: {
    message: string;
    code: string;
    challenge: string;
    timeout_ms: number;
  };
  mqtt?: any;
  websocket?: {
    url: string;
    token: string;
  };
}

export interface DeviceFingerprint {
  mac_address: string;
  serial_number: string;
  hmac_key: string;
  activation_status: boolean;
  device_fingerprint: {
    system: string;
    hostname: string;
    mac_address: string;
    machine_id: string;
  };
}

export class DeviceActivator {
  private config: Config;
  private fingerprint: DeviceFingerprint;

  constructor(config: Config, fingerprint: DeviceFingerprint) {
    this.config = config;
    this.fingerprint = fingerprint;
  }

  /**
   * Generate HMAC-SHA256 signature for activation challenge
   */
  private generateHmacSignature(challenge: string): string {
    return crypto
      .createHmac('sha256', this.fingerprint.hmac_key)
      .update(challenge, 'utf-8')
      .digest('hex');
  }

  /**
   * Attempt device activation with the server
   */
  async activateDevice(challenge: string): Promise<boolean> {
    try {
      // Calculate HMAC signature
      const hmacSignature = this.generateHmacSignature(challenge);

      // Prepare activation payload
      const payload = {
        Payload: {
          algorithm: 'hmac-sha256',
          serial_number: this.fingerprint.serial_number,
          challenge: challenge,
          hmac: hmacSignature,
        },
      };

      // Get activation URL
      const otaUrl = this.config.xiaozhi.otaUrl || 'https://api.tenclass.net/xiaozhi/ota/';
      const activateUrl = `${otaUrl}${otaUrl.endsWith('/') ? '' : '/'}activate`;

      // Set request headers
      const headers = {
        'Activation-Version': '2',
        'Device-Id': this.config.xiaozhi.deviceId,
        'Client-Id': this.config.xiaozhi.clientId,
        'Content-Type': 'application/json',
      };

      console.log('🔐 Attempting device activation...');
      console.log(`📡 Activation URL: ${activateUrl}`);
      console.log(`🔑 Serial Number: ${this.fingerprint.serial_number}`);
      console.log(`💫 Challenge: ${challenge}`);

      // Retry logic with long polling
      const maxRetries = 60; // 5 minutes total
      const retryInterval = 5000; // 5 seconds

      for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
          console.log(`⏳ Activation attempt ${attempt + 1}/${maxRetries}...`);

          const response = await fetch(activateUrl, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload),
          });

          const responseText = await response.text();
          console.log(`📥 Activation response (HTTP ${response.status}):`, responseText);

          if (response.status === 200) {
            // Activation successful
            console.log('✅ Device activation successful!');
            return true;
          } else if (response.status === 202) {
            // Waiting for user to input verification code
            console.log('⏰ Waiting for user to input verification code...');
            await new Promise(resolve => setTimeout(resolve, retryInterval));
          } else {
            // Other errors - continue retrying
            let errorMsg = 'Unknown error';
            try {
              const errorData = JSON.parse(responseText);
              errorMsg = errorData.error || `Unknown error (status: ${response.status})`;
            } catch {
              errorMsg = `Server returned error (status: ${response.status})`;
            }
            console.log(`⚠️  Server response: ${errorMsg}, continuing to wait for verification...`);
            await new Promise(resolve => setTimeout(resolve, retryInterval));
          }
        } catch (error) {
          console.log(`🌐 Network request failed: ${error}, retrying...`);
          await new Promise(resolve => setTimeout(resolve, retryInterval));
        }
      }

      console.log('❌ Activation failed: Maximum retry attempts reached');
      return false;
    } catch (error) {
      console.error('💥 Activation error:', error);
      return false;
    }
  }

  /**
   * Display activation instructions to user
   */
  displayActivationInstructions(activationData: NonNullable<ActivationResponse['activation']>): void {
    const { message, code } = activationData;
    
    console.log('\n==================');
    console.log('🔐 DEVICE ACTIVATION REQUIRED');
    console.log('==================');
    console.log(`📝 Message: ${message}`);
    console.log(`🔢 Verification Code: ${code.split('').join(' ')}`);
    console.log('🌐 Please visit https://xiaozhi.me/');
    console.log('📱 Login to your account and add this device');
    console.log(`🔑 Enter the verification code: ${code.split('').join(' ')}`);
    console.log('⏰ Waiting for activation...');
    console.log('==================\n');
  }

  /**
   * Handle activation flow when server requires activation
   */
  async handleActivationFlow(activationData: NonNullable<ActivationResponse['activation']>): Promise<boolean> {
    // Display instructions to user
    this.displayActivationInstructions(activationData);

    // Attempt activation with challenge
    return await this.activateDevice(activationData.challenge);
  }
}