const { OTAClient } = require('./dist/src/otaClient');

async function testOTA() {
  const config = {
    xiaozhi: {
      serverUrl: 'wss://api.tenclass.net/xiaozhi/v1/',
      accessToken: 'test-token',
      deviceId: 'b3:66:fa:cc:95:b9',
      clientId: 'c5d17de5-277a-47d9-8a7b-137300ea0fbc',
      otaUrl: 'https://api.tenclass.net/xiaozhi/ota/',
    },
  };

  console.log('🚀 Testing OTA configuration after activation...');
  
  try {
    const otaClient = new OTAClient(config);
    
    // 测试直接获取OTA配置
    console.log('📡 Fetching OTA configuration...');
    const otaData = await otaClient.getOTAConfig();
    
    console.log('📋 OTA Response:');
    console.log('- Has WebSocket:', !!otaData.websocket);
    console.log('- Has MQTT:', !!otaData.mqtt);
    console.log('- Has Activation:', !!otaData.activation);
    
    if (otaData.websocket) {
      console.log('- WebSocket URL:', otaData.websocket.url);
      console.log('- Token Length:', otaData.websocket.token?.length || 0);
      console.log('- Token Preview:', otaData.websocket.token?.substring(0, 20) + '...' || 'N/A');
      console.log('- Is Test Token:', otaData.websocket.token === 'test-token');
    }
    
    // 测试token获取
    console.log('\n🔑 Testing token retrieval...');
    const token = await otaClient.getWebSocketToken();
    console.log('✅ Token obtained successfully:', token.substring(0, 20) + '...');
    console.log('🔍 Token length:', token.length);
    console.log('✨ Is real token:', token !== 'test-token');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    console.error('🔍 Error details:', error);
  }
}

testOTA();