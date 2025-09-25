import { PrismaClient } from './generated/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Starting database seeding...');

  // Create admin user
  const adminPassword = await bcrypt.hash('admin123', 10);
  const admin = await prisma.user.upsert({
    where: { email: 'admin@aicamera.com' },
    update: {},
    create: {
      email: 'admin@aicamera.com',
      username: 'admin',
      password: adminPassword,
      firstName: 'System',
      lastName: 'Administrator',
      role: 'ADMIN',
    },
  });

  // Create operator user
  const operatorPassword = await bcrypt.hash('operator123', 10);
  const operator = await prisma.user.upsert({
    where: { email: 'operator@aicamera.com' },
    update: {},
    create: {
      email: 'operator@aicamera.com',
      username: 'operator',
      password: operatorPassword,
      firstName: 'System',
      lastName: 'Operator',
      role: 'OPERATOR',
    },
  });

  // Create demo user
  const userPassword = await bcrypt.hash('demo123', 10);
  const user = await prisma.user.upsert({
    where: { email: 'demo@aicamera.com' },
    update: {},
    create: {
      email: 'demo@aicamera.com',
      username: 'demo',
      password: userPassword,
      firstName: 'Demo',
      lastName: 'User',
      role: 'USER',
    },
  });

  // Create system configurations
  const systemConfigs = [
    {
      key: 'mqtt.broker.host',
      value: 'mosquitto',
      description: 'MQTT broker hostname',
      category: 'mqtt',
    },
    {
      key: 'mqtt.broker.port',
      value: '1883',
      description: 'MQTT broker port',
      category: 'mqtt',
    },
    {
      key: 'storage.max_file_size',
      value: '52428800', // 50MB
      description: 'Maximum file size in bytes',
      category: 'storage',
    },
    {
      key: 'device.heartbeat_timeout',
      value: '300', // 5 minutes
      description: 'Device heartbeat timeout in seconds',
      category: 'device',
    },
    {
      key: 'detection.retention_days',
      value: '30',
      description: 'Detection data retention period in days',
      category: 'detection',
    },
  ];

  for (const config of systemConfigs) {
    await prisma.systemConfig.upsert({
      where: { key: config.key },
      update: { value: config.value },
      create: config,
    });
  }

  // Create sample edge devices
  const devices = [
    {
      deviceId: 'cam-001',
      name: 'Entrance Camera',
      type: 'CAMERA' as const,
      location: 'Main Entrance',
      latitude: 40.7128,
      longitude: -74.0060,
      capabilities: {
        video: true,
        audio: false,
        objectDetection: true,
        faceRecognition: true,
        nightVision: true,
        ptz: false,
      },
    },
    {
      deviceId: 'cam-002',
      name: 'Parking Lot Camera',
      type: 'CAMERA' as const,
      location: 'Parking Area',
      latitude: 40.7130,
      longitude: -74.0058,
      capabilities: {
        video: true,
        audio: false,
        objectDetection: true,
        faceRecognition: false,
        nightVision: true,
        ptz: true,
      },
    },
    {
      deviceId: 'sensor-001',
      name: 'Motion Sensor',
      type: 'SENSOR' as const,
      location: 'Corridor',
      capabilities: {
        motionDetection: true,
        temperatureSensor: true,
        humiditySensor: true,
      },
    },
  ];

  for (const deviceData of devices) {
    await prisma.edgeDevice.upsert({
      where: { deviceId: deviceData.deviceId },
      update: {},
      create: deviceData,
    });
  }

  console.log('✅ Database seeding completed!');
  console.log('👤 Created users:');
  console.log('   - admin@aicamera.com (password: admin123)');
  console.log('   - operator@aicamera.com (password: operator123)');
  console.log('   - demo@aicamera.com (password: demo123)');
  console.log(`📱 Created ${devices.length} sample devices`);
  console.log(`⚙️ Created ${systemConfigs.length} system configurations`);
}

main()
  .catch((e) => {
    console.error('❌ Seeding failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });