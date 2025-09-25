import {
  Controller,
  Get,
  Post,
  Param,
  Query,
  Body,
  HttpStatus,
  HttpException,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import {
  DetectionFilterDto,
  CreateDetectionDto,
  DetectionStatsDto,
  ResponseUtil,
  Logger,
} from '@aicamera/shared';
import { DetectionService } from '../services/detection.service';
import { DetectionGateway } from '../gateways/detection.gateway';

@ApiTags('detections')
@Controller('detections')
export class DetectionController {
  private readonly logger = Logger.create('Detection-Controller');

  constructor(
    private readonly detectionService: DetectionService,
    private readonly detectionGateway: DetectionGateway,
  ) {}

  @Get()
  @ApiOperation({ summary: 'Get detections with filters' })
  @ApiResponse({ status: 200, description: 'Detections retrieved successfully' })
  async getDetections(@Query() filter: DetectionFilterDto) {
    try {
      const { limit = 10, offset = 0 } = filter;
      const result = await this.detectionService.getDetections({
        ...filter,
        hasImage: filter.hasImage === 'true' ? true : filter.hasImage === 'false' ? false : undefined,
        startDate: filter.startDate ? new Date(filter.startDate) : undefined,
        endDate: filter.endDate ? new Date(filter.endDate) : undefined,
      });
      
      const pagination = ResponseUtil.calculatePagination(
        Math.floor(offset / limit) + 1,
        limit,
        result.total
      );

      return ResponseUtil.paginated(result.detections, pagination, 'Detections retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get detections', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve detections'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get('recent')
  @ApiOperation({ summary: 'Get recent detections' })
  @ApiResponse({ status: 200, description: 'Recent detections retrieved successfully' })
  async getRecentDetections(@Query('limit') limit = 10) {
    try {
      const detections = await this.detectionService.getRecentDetections(limit);
      return ResponseUtil.success(detections, 'Recent detections retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get recent detections', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve recent detections'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get('stats')
  @ApiOperation({ summary: 'Get detection statistics' })
  @ApiResponse({ status: 200, description: 'Detection statistics retrieved successfully' })
  async getDetectionStats(@Query() statsQuery: DetectionStatsDto) {
    try {
      const stats = await this.detectionService.getDetectionStats(
        statsQuery.deviceId,
        statsQuery.startDate ? new Date(statsQuery.startDate) : undefined,
        statsQuery.endDate ? new Date(statsQuery.endDate) : undefined
      );

      return ResponseUtil.success(stats, 'Detection statistics retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get detection stats', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve detection statistics'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get('websocket/stats')
  @ApiOperation({ summary: 'Get WebSocket connection statistics' })
  @ApiResponse({ status: 200, description: 'WebSocket stats retrieved successfully' })
  async getWebSocketStats() {
    try {
      const stats = this.detectionGateway.getConnectionStats();
      return ResponseUtil.success(stats, 'WebSocket statistics retrieved successfully');
    } catch (error) {
      this.logger.error('Failed to get WebSocket stats', error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve WebSocket statistics'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get detection by ID' })
  @ApiResponse({ status: 200, description: 'Detection retrieved successfully' })
  @ApiResponse({ status: 404, description: 'Detection not found' })
  async getDetection(@Param('id') id: string) {
    try {
      const detection = await this.detectionService.getDetectionById(id);
      
      if (!detection) {
        throw new HttpException(
          ResponseUtil.notFound('Detection'),
          HttpStatus.NOT_FOUND
        );
      }

      return ResponseUtil.success(detection, 'Detection retrieved successfully');
    } catch (error) {
      if (error instanceof HttpException) {
        throw error;
      }
      
      this.logger.error(`Failed to get detection ${id}`, error);
      throw new HttpException(
        ResponseUtil.error('Failed to retrieve detection'),
        HttpStatus.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Post('manual')
  @ApiOperation({ summary: 'Manually create a detection (for testing)' })
  @ApiResponse({ status: 201, description: 'Detection created successfully' })
  async createManualDetection(@Body() detectionData: CreateDetectionDto) {
    try {
      const detection = await this.detectionService.createDetection({
        ...detectionData,
        boundingBox: detectionData.boundingBox ? {
          x: detectionData.boundingBox.x,
          y: detectionData.boundingBox.y,
          width: detectionData.boundingBox.width,
          height: detectionData.boundingBox.height,
        } : undefined,
        timestamp: detectionData.timestamp ? new Date(detectionData.timestamp) : new Date(),
      });

      // Broadcast to dashboard
      this.detectionGateway.broadcastToDashboard('dashboard_detection_update', {
        detection,
        manual: true,
        timestamp: new Date().toISOString(),
      });

      return ResponseUtil.success(detection, 'Detection created successfully');
    } catch (error) {
      this.logger.error('Failed to create manual detection', error);
      throw new HttpException(
        ResponseUtil.error('Failed to create detection', [error.message]),
        HttpStatus.BAD_REQUEST
      );
    }
  }
}