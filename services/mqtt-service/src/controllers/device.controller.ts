import {
  Controller,
  Get,
  Post,
  Put,
  Param,
  Query,
  Body,
  HttpStatus,
  HttpException,
  UseGuards,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiBearerAuth } from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';
import {
  DeviceFilterDto,
  CreateDeviceDto,
  UpdateDeviceDto,
  DeviceHeartbeatDto,
  ResponseUtil,
  Logger,
} from '@aicamera/shared';
import { DeviceService } from '../services/device.service';
import { MqttClientService } from '../services/mqtt-client.service';

@ApiTags('devices')
@Controller('devices')
@UseGuards() // Add authentication guard here when implemented
export class DeviceController {
  private readonly logger = Logger.create('Device-Controller');

  constructor(
    private readonly deviceService: DeviceService,
    private readonly mqttClientService: MqttClientService,
  ) {}

  @Get()
  @ApiOperation({ summary: 'Get all devices' })
  @ApiResponse({ status: 200, description: 'Devices retrieved successfully' })
  @Throttle({ long: { limit: 50, ttl: 60000 } })
  async getAllDevices(@Query() filter: DeviceFilterDto) {
    try {
      const { limit = 10, offset = 0 } = filter;
      const result = await this.deviceService.getAllDevices(limit, offset);
      
      const pagination = ResponseUtil.calculatePagination(
        Math.floor(offset / limit) + 1,
        limit,
        result.total
      );

      return ResponseUtil.paginated(result.devices, pagination, 'Devices retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get devices', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve devices'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get('stats')
  @ApiOperation({ summary: 'Get device statistics' })
  @ApiResponse({ status: 200, description: 'Device statistics retrieved successfully' })
  async getDeviceStats() {
    try {
      const stats = await this.deviceService.getDeviceStats();
      return ResponseUtil.success(stats, 'Device statistics retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get device stats', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve device statistics'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get(':deviceId')
  @ApiOperation({ summary: 'Get device by ID' })
  @ApiResponse({ status: 200, description: 'Device retrieved successfully' })
  @ApiResponse({ status: 404, description: 'Device not found' })
  async getDevice(@Param('deviceId') deviceId: string) {
    try {
      const device = await this.deviceService.getDevice(deviceId);
      
      if (!device) {
        throw new HttpException(
          ResponseUtil.notFound('Device'),
          HttpStatus.NOT_FOUND
        );
      }

      return ResponseUtil.success(device, 'Device retrieved successfully');
    } catch (error) {
      if (error instanceof HttpException) {
        throw error;
      }
      
      this.logger.error(`Failed to get device ${deviceId}`, error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve device'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get(':deviceId/config')
  @ApiOperation({ summary: 'Get device configuration' })
  @ApiResponse({ status: 200, description: 'Device configuration retrieved successfully' })
  @ApiResponse({ status: 404, description: 'Device not found' })
  async getDeviceConfig(@Param('deviceId') deviceId: string) {
    try {
      const config = await this.deviceService.getDeviceConfig(deviceId);
      return ResponseUtil.success(config, 'Device configuration retrieved successfully');
    } catch (error) {
      if (error.name === 'NotFoundException') {
        throw new HttpException(
          ResponseUtil.notFound('Device'),
          HttpStatus.NOT_FOUND
        );
      }
      
      this.logger.error(`Failed to get device config for ${deviceId}`, error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve device configuration'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Post(':deviceId/config/send')
  @ApiOperation({ summary: 'Send configuration to device via MQTT' })
  @ApiResponse({ status: 200, description: 'Configuration sent successfully' })
  @ApiResponse({ status: 404, description: 'Device not found' })
  @Throttle({ short: { limit: 5, ttl: 60000 } })
  async sendDeviceConfig(@Param('deviceId') deviceId: string) {
    try {
      await this.mqttClientService.sendDeviceConfig(deviceId);
      return ResponseUtil.success(null, 'Configuration sent to device successfully');
    } catch (error) {
      this.logger.error(`Failed to send config to device ${deviceId}`, error);
      throw new HttpException(
        ResponseUtil.error('Failed to send configuration to device'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Post('register')
  @ApiOperation({ summary: 'Register a new device (manual registration)' })
  @ApiResponse({ status: 201, description: 'Device registered successfully' })
  @ApiResponse({ status: 400, description: 'Invalid device data' })
  @Throttle({ short: { limit: 10, ttl: 60000 } })
  async registerDevice(@Body() deviceData: CreateDeviceDto) {
    try {
      const device = await this.deviceService.registerDevice(deviceData);
      return ResponseUtil.success(device, 'Device registered successfully');
    } catch (error) {
      this.logger.error('Failed to register device', error);
      throw new HttpException(
        ResponseUtil.error('Failed to register device', [error.message]),
        HttpStatus.BAD_REQUEST
      );
    }
  }

  @Put(':deviceId')
  @ApiOperation({ summary: 'Update device information' })
  @ApiResponse({ status: 200, description: 'Device updated successfully' })
  @ApiResponse({ status: 404, description: 'Device not found' })
  async updateDevice(
    @Param('deviceId') deviceId: string,
    @Body() updateData: UpdateDeviceDto
  ) {
    try {
      // Check if device exists
      const existingDevice = await this.deviceService.getDevice(deviceId);
      if (!existingDevice) {
        throw new HttpException(
          ResponseUtil.notFound('Device'),
          HttpStatus.NOT_FOUND
        );
      }

      // Update device status if provided
      if (updateData.status) {
        await this.deviceService.updateDeviceStatus(
          deviceId,
          updateData.status,
          updateData.metadata
        );
      }

      const updatedDevice = await this.deviceService.getDevice(deviceId);
      return ResponseUtil.success(updatedDevice, 'Device updated successfully');
    } catch (error) {
      if (error instanceof HttpException) {
        throw error;
      }
      
      this.logger.error(`Failed to update device ${deviceId}`, error);
      throw new HttpException(
        ResponseUtil.error('Failed to update device'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Post('system/broadcast')
  @ApiOperation({ summary: 'Broadcast system message to all devices' })
  @ApiResponse({ status: 200, description: 'Message broadcasted successfully' })
  @Throttle({ short: { limit: 2, ttl: 60000 } })
  async broadcastSystemMessage(@Body() message: any) {
    try {
      await this.mqttClientService.broadcastSystemMessage(message);
      return ResponseUtil.success(null, 'System message broadcasted successfully');
    } catch (error) {
      this.logger.error('Failed to broadcast system message', error);
      throw new HttpException(
        ResponseUtil.error('Failed to broadcast system message'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Post('system/alert')
  @ApiOperation({ summary: 'Send system alert to all devices' })
  @ApiResponse({ status: 200, description: 'Alert sent successfully' })
  @Throttle({ short: { limit: 5, ttl: 60000 } })
  async sendSystemAlert(@Body() alert: any) {
    try {
      await this.mqttClientService.sendSystemAlert(alert);
      return ResponseUtil.success(null, 'System alert sent successfully');
    } catch (error) {
      this.logger.error('Failed to send system alert', error);
      throw new HttpException(
        ResponseUtil.error('Failed to send system alert'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get('mqtt/status')
  @ApiOperation({ summary: 'Get MQTT client status' })
  @ApiResponse({ status: 200, description: 'MQTT status retrieved successfully' })
  async getMqttStatus() {
    try {
      const status = {
        ...this.mqttClientService.getClientInfo(),
        timestamp: new Date().toISOString(),
      };

      return ResponseUtil.success(status, 'MQTT status retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get MQTT status', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve MQTT status'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }
}