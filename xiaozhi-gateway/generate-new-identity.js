const crypto = require('crypto');
const fs = require('fs');
const os = require('os');

function generateNewDeviceIdentity() {
  // 生成随机MAC地址
  const macAddr = Array.from({length: 6}, () => 
    Math.floor(Math.random() * 256).toString(16).padStart(2, '0')
  ).join(':');
  
  // 生成序列号
  const serialNumber = `SN-${crypto.randomBytes(4).toString('hex').toUpperCase()}-${macAddr.replace(/:/g, '')}`;
  
  // 生成HMAC密钥
  const hmacKey = crypto.randomBytes(32).toString('hex');
  
  // 生成machine_id
  const machineId = crypto.randomUUID().toUpperCase();
  
  const newIdentity = {
    mac_address: macAddr,
    serial_number: serialNumber,
    hmac_key: hmacKey,
    activation_status: false,
    device_fingerprint: {
      system: os.type(),
      hostname: os.hostname(),
      mac_address: macAddr,
      machine_id: machineId
    }
  };
  
  console.log('🆕 Generated new device identity:');
  console.log('MAC Address:', macAddr);
  console.log('Serial Number:', serialNumber);
  console.log('HMAC Key:', hmacKey);
  console.log('Machine ID:', machineId);
  
  return newIdentity;
}

function updateConfigWithNewIdentity(newIdentity) {
  const configPath = '/Users/good/Desktop/Zoe/xiaozhi-gateway/.env';
  const efusePath = '/Users/good/Desktop/Zoe/xiaozhi/pc_xiaozhi/third_party/py-xiaozhi/config/efuse.json';
  
  // 更新efuse.json
  console.log('📝 Updating efuse.json...');
  fs.writeFileSync(efusePath, JSON.stringify(newIdentity, null, 2));
  
  // 读取并更新.env文件
  console.log('📝 Updating .env file...');
  let envContent = fs.readFileSync(configPath, 'utf8');
  
  // 更新DEVICE_ID
  envContent = envContent.replace(
    /XIAOZHI_DEVICE_ID=.*/,
    `XIAOZHI_DEVICE_ID=${newIdentity.mac_address}`
  );
  
  fs.writeFileSync(configPath, envContent);
  
  console.log('✅ Configuration files updated successfully');
}

// 生成新身份
const newIdentity = generateNewDeviceIdentity();

// 更新配置文件
updateConfigWithNewIdentity(newIdentity);

console.log('\n🎯 New device identity generated and configured!');
console.log('🔄 Please restart the gateway service to use the new identity.');
console.log('🌐 The server should now send an activation challenge.');