const WebSocket = require('ws');
const fetch = require('node-fetch');

async function testActivation() {
  try {
    console.log('🚀 Starting activation test...');
    
    // 1. 创建会话
    console.log('📝 Creating session...');
    const sessionResponse = await fetch('http://localhost:3000/session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        userId: 'activation-test-user',
      }),
    });

    if (!sessionResponse.ok) {
      throw new Error(`Failed to create session: ${sessionResponse.status}`);
    }

    const sessionData = await sessionResponse.json();
    console.log(`✅ Session created: ${sessionData.sessionId}`);
    
    // 2. 连接WebSocket - 这会触发OTA token获取和可能的激活流程
    console.log('🔌 Connecting to WebSocket...');
    const ws = new WebSocket(sessionData.wsUrl);
    
    ws.on('open', () => {
      console.log('🟢 WebSocket connected successfully');
      console.log('⏳ Waiting for potential activation process...');
    });
    
    ws.on('message', (data) => {
      try {
        const message = JSON.parse(data.toString());
        console.log('📨 Received message:', message);
      } catch (e) {
        console.log('📨 Received binary data:', data.length, 'bytes');
      }
    });
    
    ws.on('error', (error) => {
      console.error('❌ WebSocket error:', error);
    });
    
    ws.on('close', (code, reason) => {
      console.log(`🔴 WebSocket closed: ${code} - ${reason}`);
    });

    // 保持连接一段时间以观察激活流程
    setTimeout(() => {
      console.log('⏰ Test timeout, closing connection...');
      ws.close();
    }, 30000); // 30秒超时

  } catch (error) {
    console.error('💥 Test failed:', error);
  }
}

// 运行测试
testActivation();