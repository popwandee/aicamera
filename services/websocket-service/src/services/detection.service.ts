import { Injectable, Inject } from '@nestjs/common';
import { PrismaClient } from '../../../database/generated/client';
import { RedisClientType } from 'redis';
import {
  Logger,
  IDetection,
  IDetectionRequest,
  IDetectionFilter,
  IDetectionStats,
  DetectionType,
  ResponseUtil,
  ValidationUtil,
} from '@aicamera/shared';

@Injectable()
export class DetectionService {
  private readonly logger = Logger.create('Detection-Service');

  constructor(
    @Inject('PRISMA_CLIENT') private readonly prisma: PrismaClient,
    @Inject('REDIS_CLIENT') private readonly redis: RedisClientType,
  ) {}

  async createDetection(detectionData: IDetectionRequest): Promise<IDetection> {
    try {
      // Validate detection data
      if (!ValidationUtil.isValidConfidence(detectionData.confidence)) {
        throw new Error('Invalid confidence value');
      }

      if (!ValidationUtil.isValidDeviceId(detectionData.deviceId)) {
        throw new Error('Invalid device ID');
      }

      // Create detection record
      const detection = await this.prisma.detection.create({
        data: {
          deviceId: detectionData.deviceId,
          type: detectionData.type,
          confidence: detectionData.confidence,
          x: detectionData.boundingBox?.x,
          y: detectionData.boundingBox?.y,
          width: detectionData.boundingBox?.width,
          height: detectionData.boundingBox?.height,
          label: detectionData.label,
          classes: detectionData.classes || [],
          rawData: detectionData.rawData,
          imageId: detectionData.imageId,
          trackingId: detectionData.trackingId,
        },
        include: {
          device: {
            select: {
              deviceId: true,
              name: true,
              type: true,
              location: true,
            },
          },
        },
      });

      // Cache recent detection for quick access
      await this.cacheRecentDetection(detection);

      // Update device's last seen timestamp
      await this.prisma.edgeDevice.update({
        where: { id: detection.deviceId },
        data: { lastSeen: new Date() },
      });

      this.logger.debug(`Detection created: ${detection.id} from device ${detectionData.deviceId}`);

      return detection as IDetection;
    } catch (error) {
      this.logger.error('Failed to create detection', error);
      throw error;
    }
  }

  async createBulkDetections(detectionsData: IDetectionRequest[]): Promise<IDetection[]> {
    try {
      // Validate all detections
      for (const detection of detectionsData) {
        if (!ValidationUtil.isValidConfidence(detection.confidence)) {
          throw new Error('Invalid confidence value in bulk data');
        }
        if (!ValidationUtil.isValidDeviceId(detection.deviceId)) {
          throw new Error('Invalid device ID in bulk data');
        }
      }

      // Create all detections in a transaction
      const detections = await this.prisma.$transaction(
        detectionsData.map(detectionData =>
          this.prisma.detection.create({
            data: {
              deviceId: detectionData.deviceId,
              type: detectionData.type,
              confidence: detectionData.confidence,
              x: detectionData.boundingBox?.x,
              y: detectionData.boundingBox?.y,
              width: detectionData.boundingBox?.width,
              height: detectionData.boundingBox?.height,
              label: detectionData.label,
              classes: detectionData.classes || [],
              rawData: detectionData.rawData,
              imageId: detectionData.imageId,
              trackingId: detectionData.trackingId,
            },
            include: {
              device: {
                select: {
                  deviceId: true,
                  name: true,
                  type: true,
                  location: true,
                },
              },
            },
          })
        )
      );

      // Cache all detections
      for (const detection of detections) {
        await this.cacheRecentDetection(detection);
      }

      // Update device's last seen timestamp
      const deviceIds = [...new Set(detectionsData.map(d => d.deviceId))];
      for (const deviceId of deviceIds) {
        await this.prisma.edgeDevice.update({
          where: { deviceId },
          data: { lastSeen: new Date() },
        });
      }

      this.logger.info(`Bulk detections created: ${detections.length} detections`);

      return detections as IDetection[];
    } catch (error) {
      this.logger.error('Failed to create bulk detections', error);
      throw error;
    }
  }

  async getDetections(filter: IDetectionFilter): Promise<{ detections: IDetection[]; total: number }> {
    try {
      const where: any = {};

      if (filter.deviceId) {
        where.device = { deviceId: filter.deviceId };
      }

      if (filter.type) {
        where.type = filter.type;
      }

      if (filter.minConfidence) {
        where.confidence = { gte: filter.minConfidence };
      }

      if (filter.startDate || filter.endDate) {
        where.createdAt = {};
        if (filter.startDate) where.createdAt.gte = filter.startDate;
        if (filter.endDate) where.createdAt.lte = filter.endDate;
      }

      if (filter.label) {
        where.label = { contains: filter.label, mode: 'insensitive' };
      }

      if (filter.trackingId) {
        where.trackingId = filter.trackingId;
      }

      if (filter.hasImage !== undefined) {
        where.imageId = filter.hasImage ? { not: null } : null;
      }

      const [detections, total] = await Promise.all([
        this.prisma.detection.findMany({
          where,
          include: {
            device: {
              select: {
                deviceId: true,
                name: true,
                type: true,
                location: true,
              },
            },
            image: {
              select: {
                id: true,
                filename: true,
                path: true,
                thumbnailPath: true,
              },
            },
          },
          orderBy: { createdAt: 'desc' },
          take: filter.limit || 10,
          skip: filter.offset || 0,
        }),
        this.prisma.detection.count({ where }),
      ]);

      return {
        detections: detections as IDetection[],
        total,
      };
    } catch (error) {
      this.logger.error('Failed to get detections', error);
      throw error;
    }
  }

  async getDetectionById(id: string): Promise<IDetection | null> {
    try {
      const detection = await this.prisma.detection.findUnique({
        where: { id },
        include: {
          device: {
            select: {
              deviceId: true,
              name: true,
              type: true,
              location: true,
            },
          },
          image: {
            select: {
              id: true,
              filename: true,
              path: true,
              thumbnailPath: true,
              previewPath: true,
            },
          },
        },
      });

      return detection as IDetection;
    } catch (error) {
      this.logger.error(`Failed to get detection ${id}`, error);
      throw error;
    }
  }

  async getRecentDetections(limit = 10): Promise<IDetection[]> {
    try {
      // Try to get from cache first
      const cached = await this.getCachedRecentDetections(limit);
      if (cached.length > 0) {
        return cached;
      }

      // Get from database
      const detections = await this.prisma.detection.findMany({
        include: {
          device: {
            select: {
              deviceId: true,
              name: true,
              type: true,
              location: true,
            },
          },
        },
        orderBy: { createdAt: 'desc' },
        take: limit,
      });

      return detections as IDetection[];
    } catch (error) {
      this.logger.error('Failed to get recent detections', error);
      throw error;
    }
  }

  async getDetectionStats(deviceId?: string, startDate?: Date, endDate?: Date): Promise<IDetectionStats> {
    try {
      const where: any = {};

      if (deviceId) {
        where.device = { deviceId };
      }

      if (startDate || endDate) {
        where.createdAt = {};
        if (startDate) where.createdAt.gte = startDate;
        if (endDate) where.createdAt.lte = endDate;
      }

      const [
        total,
        byType,
        byDevice,
        avgConfidence,
        today,
        thisWeek,
        thisMonth,
      ] = await Promise.all([
        this.prisma.detection.count({ where }),
        this.prisma.detection.groupBy({
          by: ['type'],
          where,
          _count: true,
        }),
        this.prisma.detection.groupBy({
          by: ['deviceId'],
          where,
          _count: true,
          _avg: { confidence: true },
        }),
        this.prisma.detection.aggregate({
          where,
          _avg: { confidence: true },
        }),
        this.prisma.detection.count({
          where: {
            ...where,
            createdAt: { gte: new Date(new Date().setHours(0, 0, 0, 0)) },
          },
        }),
        this.prisma.detection.count({
          where: {
            ...where,
            createdAt: { gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) },
          },
        }),
        this.prisma.detection.count({
          where: {
            ...where,
            createdAt: { gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) },
          },
        }),
      ]);

      // Get device names for the device stats
      const deviceIds = byDevice.map(d => d.deviceId);
      const devices = await this.prisma.edgeDevice.findMany({
        where: { id: { in: deviceIds } },
        select: { id: true, deviceId: true, name: true },
      });

      const deviceIdMap = devices.reduce((acc, device) => {
        acc[device.id] = device.deviceId;
        return acc;
      }, {} as Record<string, string>);

      return {
        totalDetections: total,
        detectionsByType: byType.reduce((acc, item) => {
          acc[item.type as DetectionType] = item._count;
          return acc;
        }, {} as Record<DetectionType, number>),
        detectionsByDevice: byDevice.reduce((acc, item) => {
          const deviceId = deviceIdMap[item.deviceId];
          if (deviceId) {
            acc[deviceId] = item._count;
          }
          return acc;
        }, {} as Record<string, number>),
        averageConfidence: avgConfidence._avg.confidence || 0,
        detectionsToday: today,
        detectionsThisWeek: thisWeek,
        detectionsThisMonth: thisMonth,
      };
    } catch (error) {
      this.logger.error('Failed to get detection stats', error);
      throw error;
    }
  }

  // Redis cache methods
  private async cacheRecentDetection(detection: any): Promise<void> {
    try {
      const cacheKey = 'recent_detections';
      const detectionData = JSON.stringify(detection);
      
      // Add to sorted set with timestamp as score
      await this.redis.zAdd(cacheKey, {
        score: Date.now(),
        value: detectionData,
      });

      // Keep only the most recent 100 detections
      await this.redis.zRemRangeByRank(cacheKey, 0, -101);
      
      // Set expiration
      await this.redis.expire(cacheKey, 300); // 5 minutes
    } catch (error) {
      this.logger.error('Failed to cache recent detection', error);
    }
  }

  private async getCachedRecentDetections(limit: number): Promise<IDetection[]> {
    try {
      const cacheKey = 'recent_detections';
      const cached = await this.redis.zRevRange(cacheKey, 0, limit - 1);
      
      return cached.map(item => JSON.parse(item));
    } catch (error) {
      this.logger.error('Failed to get cached recent detections', error);
      return [];
    }
  }
}