import { Controller, Get, Inject } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { PrismaClient } from '../../../database/generated/client';
import { RedisClientType } from 'redis';
import { Logger, ResponseUtil } from '@aicamera/shared';
import { MqttClientService } from '../services/mqtt-client.service';

@ApiTags('health')
@Controller('health')
export class HealthController {
  private readonly logger = Logger.create('Health-Controller');

  constructor(
    @Inject('PRISMA_CLIENT') private readonly prisma: PrismaClient,
    @Inject('REDIS_CLIENT') private readonly redis: RedisClientType,
    @Inject('MQTT_CLIENT') private readonly mqttClient: MqttClientService,
  ) {}

  @Get()
  @ApiOperation({ summary: 'Get service health status' })
  @ApiResponse({ status: 200, description: 'Health status retrieved successfully' })
  async getHealth() {
    const startTime = Date.now();
    
    try {
      // Check database connection
      const dbCheck = await this.checkDatabase();
      
      // Check Redis connection
      const redisCheck = await this.checkRedis();
      
      // Check MQTT connection
      const mqttCheck = this.checkMqtt();

      const responseTime = Date.now() - startTime;

      const health = {
        status: dbCheck.status === 'up' && redisCheck.status === 'up' && mqttCheck.status === 'up' 
          ? 'healthy' : 'degraded',
        timestamp: new Date().toISOString(),
        service: 'mqtt-service',
        version: process.env.npm_package_version || '1.0.0',
        uptime: process.uptime(),
        responseTime,
        dependencies: {
          database: dbCheck,
          redis: redisCheck,
          mqtt: mqttCheck,
        },
        system: {
          nodeVersion: process.version,
          platform: process.platform,
          arch: process.arch,
          memoryUsage: process.memoryUsage(),
          cpuUsage: process.cpuUsage(),
        },
      };

      return ResponseUtil.success(health, 'Health status retrieved successfully');
    } catch (error) {
      this.logger.error('Health check failed', error);
      
      return ResponseUtil.error('Health check failed', [error.message]);
    }
  }

  @Get('ready')
  @ApiOperation({ summary: 'Check if service is ready' })
  @ApiResponse({ status: 200, description: 'Service readiness status' })
  async getReadiness() {
    try {
      // Basic readiness checks
      const dbStatus = await this.checkDatabase();
      const redisStatus = await this.checkRedis();

      const isReady = dbStatus.status === 'up' && redisStatus.status === 'up';

      const readiness = {
        ready: isReady,
        timestamp: new Date().toISOString(),
        checks: {
          database: dbStatus.status === 'up',
          redis: redisStatus.status === 'up',
        },
      };

      return ResponseUtil.success(readiness, isReady ? 'Service is ready' : 'Service is not ready');
    } catch (error) {
      this.logger.error('Readiness check failed', error);
      return ResponseUtil.error('Readiness check failed');
    }
  }

  @Get('live')
  @ApiOperation({ summary: 'Check if service is alive' })
  @ApiResponse({ status: 200, description: 'Service liveness status' })
  async getLiveness() {
    // Simple liveness check - if we can respond, we're alive
    return ResponseUtil.success(
      {
        alive: true,
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
      },
      'Service is alive'
    );
  }

  private async checkDatabase(): Promise<{ status: 'up' | 'down'; responseTime?: number; error?: string }> {
    const startTime = Date.now();
    
    try {
      await this.prisma.$queryRaw`SELECT 1`;
      
      return {
        status: 'up',
        responseTime: Date.now() - startTime,
      };
    } catch (error) {
      return {
        status: 'down',
        responseTime: Date.now() - startTime,
        error: error.message,
      };
    }
  }

  private async checkRedis(): Promise<{ status: 'up' | 'down'; responseTime?: number; error?: string }> {
    const startTime = Date.now();
    
    try {
      await this.redis.ping();
      
      return {
        status: 'up',
        responseTime: Date.now() - startTime,
      };
    } catch (error) {
      return {
        status: 'down',
        responseTime: Date.now() - startTime,
        error: error.message,
      };
    }
  }

  private checkMqtt(): { status: 'up' | 'down'; connected: boolean; error?: string } {
    try {
      const isConnected = this.mqttClient.isConnected();
      
      return {
        status: isConnected ? 'up' : 'down',
        connected: isConnected,
      };
    } catch (error) {
      return {
        status: 'down',
        connected: false,
        error: error.message,
      };
    }
  }
}