import { Injectable, Inject, NotFoundException } from '@nestjs/common';
import { PrismaClient } from '../../../database/generated/client';
import { RedisClientType } from 'redis';
import {
  Logger,
  IEdgeDevice,
  IDeviceRegistration,
  IDeviceHeartbeat,
  IDeviceLog,
  DeviceStatus,
  ResponseUtil,
  ValidationUtil,
} from '@aicamera/shared';

@Injectable()
export class DeviceService {
  private readonly logger = Logger.create('Device-Service');

  constructor(
    @Inject('PRISMA_CLIENT') private readonly prisma: PrismaClient,
    @Inject('REDIS_CLIENT') private readonly redis: RedisClientType,
  ) {}

  async registerDevice(deviceData: IDeviceRegistration): Promise<IEdgeDevice> {
    try {
      // Validate device data
      if (!ValidationUtil.isValidDeviceId(deviceData.deviceId)) {
        throw new Error('Invalid device ID format');
      }

      // Check if device already exists
      let device = await this.prisma.edgeDevice.findUnique({
        where: { deviceId: deviceData.deviceId },
      });

      if (device) {
        // Update existing device
        device = await this.prisma.edgeDevice.update({
          where: { deviceId: deviceData.deviceId },
          data: {
            name: deviceData.name,
            type: deviceData.type,
            status: DeviceStatus.ONLINE,
            location: deviceData.location,
            latitude: deviceData.latitude,
            longitude: deviceData.longitude,
            capabilities: deviceData.capabilities,
            metadata: deviceData.metadata,
            lastSeen: new Date(),
            lastHeartbeat: new Date(),
          },
        });

        this.logger.info(`Device updated: ${deviceData.deviceId}`);
      } else {
        // Create new device
        device = await this.prisma.edgeDevice.create({
          data: {
            deviceId: deviceData.deviceId,
            name: deviceData.name,
            type: deviceData.type,
            status: DeviceStatus.ONLINE,
            location: deviceData.location,
            latitude: deviceData.latitude,
            longitude: deviceData.longitude,
            capabilities: deviceData.capabilities,
            metadata: deviceData.metadata,
            lastSeen: new Date(),
            lastHeartbeat: new Date(),
          },
        });

        this.logger.info(`New device registered: ${deviceData.deviceId}`);
      }

      // Cache device info in Redis
      await this.cacheDeviceInfo(device);

      // Create registration log
      await this.createDeviceLog({
        id: '',
        deviceId: deviceData.deviceId,
        level: 'INFO',
        message: device.id === device.id ? 'Device updated' : 'Device registered',
        data: { registration: deviceData },
        createdAt: new Date(),
      });

      return device as IEdgeDevice;
    } catch (error) {
      this.logger.error(`Failed to register device ${deviceData.deviceId}`, error);
      throw error;
    }
  }

  async updateHeartbeat(heartbeatData: IDeviceHeartbeat): Promise<void> {
    try {
      const device = await this.prisma.edgeDevice.findUnique({
        where: { deviceId: heartbeatData.deviceId },
      });

      if (!device) {
        throw new NotFoundException(`Device ${heartbeatData.deviceId} not found`);
      }

      // Update device heartbeat
      await this.prisma.edgeDevice.update({
        where: { deviceId: heartbeatData.deviceId },
        data: {
          status: heartbeatData.status,
          lastHeartbeat: heartbeatData.timestamp,
          lastSeen: heartbeatData.timestamp,
          ipAddress: heartbeatData.networkInfo?.ipAddress,
          macAddress: heartbeatData.networkInfo?.macAddress,
        },
      });

      // Update cached device status
      await this.updateCachedDeviceStatus(heartbeatData.deviceId, heartbeatData.status);

      // Store heartbeat data in Redis for quick access
      const heartbeatKey = `heartbeat:${heartbeatData.deviceId}`;
      await this.redis.set(heartbeatKey, JSON.stringify(heartbeatData), { EX: 300 }); // 5 minutes TTL

      this.logger.debug(`Heartbeat updated for device ${heartbeatData.deviceId}`);
    } catch (error) {
      this.logger.error(`Failed to update heartbeat for device ${heartbeatData.deviceId}`, error);
      throw error;
    }
  }

  async updateDeviceStatus(deviceId: string, status: DeviceStatus, metadata?: any): Promise<void> {
    try {
      const device = await this.prisma.edgeDevice.findUnique({
        where: { deviceId },
      });

      if (!device) {
        throw new NotFoundException(`Device ${deviceId} not found`);
      }

      const previousStatus = device.status;

      await this.prisma.edgeDevice.update({
        where: { deviceId },
        data: {
          status,
          lastSeen: new Date(),
          metadata: metadata ? { ...device.metadata, ...metadata } : device.metadata,
        },
      });

      // Update cached device status
      await this.updateCachedDeviceStatus(deviceId, status);

      // Log status change
      if (previousStatus !== status) {
        await this.createDeviceLog({
          id: '',
          deviceId,
          level: 'INFO',
          message: `Device status changed from ${previousStatus} to ${status}`,
          data: { previousStatus, newStatus: status, metadata },
          createdAt: new Date(),
        });

        this.logger.info(`Device ${deviceId} status changed: ${previousStatus} -> ${status}`);
      }
    } catch (error) {
      this.logger.error(`Failed to update device status for ${deviceId}`, error);
      throw error;
    }
  }

  async createDeviceLog(logData: IDeviceLog): Promise<void> {
    try {
      await this.prisma.deviceLog.create({
        data: {
          deviceId: logData.deviceId,
          level: logData.level,
          message: logData.message,
          data: logData.data,
        },
      });

      this.logger.debug(`Device log created for ${logData.deviceId}: ${logData.message}`);
    } catch (error) {
      this.logger.error(`Failed to create device log for ${logData.deviceId}`, error);
      throw error;
    }
  }

  async getDevice(deviceId: string): Promise<IEdgeDevice | null> {
    try {
      // Try to get from cache first
      const cachedDevice = await this.getCachedDeviceInfo(deviceId);
      if (cachedDevice) {
        return cachedDevice;
      }

      // Get from database
      const device = await this.prisma.edgeDevice.findUnique({
        where: { deviceId },
        include: {
          deviceLogs: {
            orderBy: { createdAt: 'desc' },
            take: 10,
          },
        },
      });

      if (device) {
        // Cache the device info
        await this.cacheDeviceInfo(device);
        return device as IEdgeDevice;
      }

      return null;
    } catch (error) {
      this.logger.error(`Failed to get device ${deviceId}`, error);
      throw error;
    }
  }

  async getDeviceConfig(deviceId: string): Promise<any> {
    try {
      const device = await this.getDevice(deviceId);
      if (!device) {
        throw new NotFoundException(`Device ${deviceId} not found`);
      }

      // Get system configurations
      const systemConfigs = await this.prisma.systemConfig.findMany({
        where: {
          category: { in: ['mqtt', 'device', 'system'] },
        },
      });

      const config = {
        device: {
          id: device.deviceId,
          name: device.name,
          type: device.type,
          capabilities: device.capabilities,
        },
        system: systemConfigs.reduce((acc, config) => {
          acc[config.key] = config.value;
          return acc;
        }, {} as Record<string, string>),
        mqtt: {
          heartbeatInterval: 30000, // 30 seconds
          statusInterval: 60000,    // 60 seconds
          logLevel: 'INFO',
        },
        timestamp: new Date().toISOString(),
      };

      return config;
    } catch (error) {
      this.logger.error(`Failed to get device config for ${deviceId}`, error);
      throw error;
    }
  }

  async getAllDevices(limit = 10, offset = 0): Promise<{ devices: IEdgeDevice[]; total: number }> {
    try {
      const [devices, total] = await Promise.all([
        this.prisma.edgeDevice.findMany({
          take: limit,
          skip: offset,
          orderBy: { name: 'asc' },
        }),
        this.prisma.edgeDevice.count(),
      ]);

      return {
        devices: devices as IEdgeDevice[],
        total,
      };
    } catch (error) {
      this.logger.error('Failed to get all devices', error);
      throw error;
    }
  }

  async getDeviceStats(): Promise<any> {
    try {
      const [total, online, offline, byType] = await Promise.all([
        this.prisma.edgeDevice.count(),
        this.prisma.edgeDevice.count({ where: { status: DeviceStatus.ONLINE } }),
        this.prisma.edgeDevice.count({ where: { status: DeviceStatus.OFFLINE } }),
        this.prisma.edgeDevice.groupBy({
          by: ['type'],
          _count: true,
        }),
      ]);

      return {
        totalDevices: total,
        onlineDevices: online,
        offlineDevices: offline,
        connectingDevices: total - online - offline,
        devicesByType: byType.reduce((acc, item) => {
          acc[item.type] = item._count;
          return acc;
        }, {} as Record<string, number>),
      };
    } catch (error) {
      this.logger.error('Failed to get device stats', error);
      throw error;
    }
  }

  // Redis cache methods
  private async cacheDeviceInfo(device: any): Promise<void> {
    try {
      const cacheKey = `device:${device.deviceId}`;
      await this.redis.set(cacheKey, JSON.stringify(device), { EX: 300 }); // 5 minutes TTL
    } catch (error) {
      this.logger.error(`Failed to cache device info for ${device.deviceId}`, error);
    }
  }

  private async getCachedDeviceInfo(deviceId: string): Promise<IEdgeDevice | null> {
    try {
      const cacheKey = `device:${deviceId}`;
      const cached = await this.redis.get(cacheKey);
      return cached ? JSON.parse(cached) : null;
    } catch (error) {
      this.logger.error(`Failed to get cached device info for ${deviceId}`, error);
      return null;
    }
  }

  private async updateCachedDeviceStatus(deviceId: string, status: DeviceStatus): Promise<void> {
    try {
      const cacheKey = `device:${deviceId}`;
      const cached = await this.redis.get(cacheKey);
      
      if (cached) {
        const device = JSON.parse(cached);
        device.status = status;
        device.lastSeen = new Date();
        await this.redis.set(cacheKey, JSON.stringify(device), { EX: 300 });
      }
    } catch (error) {
      this.logger.error(`Failed to update cached device status for ${deviceId}`, error);
    }
  }

  // Device monitoring methods
  async checkOfflineDevices(): Promise<void> {
    try {
      const offlineThreshold = new Date(Date.now() - 10 * 60 * 1000); // 10 minutes ago
      
      await this.prisma.edgeDevice.updateMany({
        where: {
          lastHeartbeat: { lt: offlineThreshold },
          status: { not: DeviceStatus.OFFLINE },
        },
        data: {
          status: DeviceStatus.OFFLINE,
        },
      });

      this.logger.debug('Checked and updated offline devices');
    } catch (error) {
      this.logger.error('Failed to check offline devices', error);
    }
  }
}