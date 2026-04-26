import {
  Controller,
  Get,
  Post,
  Put,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  ParseUUIDPipe,
  NotFoundException,
  StreamableFile,
} from '@nestjs/common';
import * as fs from 'fs';
import * as path from 'path';
import { DeviceService } from './device.service';
import { Camera, Detection, CameraHealth } from '../entities';

@Controller()
export class DeviceController {
  constructor(private readonly deviceService: DeviceService) {}

  @Get('cameras')
  async getCameras() {
    return this.deviceService.findAllCameras();
  }

  @Get('cameras/summary')
  async getCameraSummary() {
    return this.deviceService.getCameraSummary();
  }

  @Get('cameras/analytics/run')
  async runDailyAnalytics() {
    await this.deviceService.runUpdateDailyAnalytics();
    return { ok: true };
  }

  @Get('cameras/edge-status')
  async getCamerasEdgeStatus() {
    return this.deviceService.findCamerasWithLatestHealth();
  }

  @Get('cameras/:id')
  async getCamera(@Param('id', ParseUUIDPipe) id: string) {
    const camera = await this.deviceService.findCameraById(id);
    if (!camera) return { error: 'Not found' };
    return camera;
  }

  @Post('cameras/register')
  async registerCamera(
    @Body() body: { camera_id: string; checkpoint_id: string; timestamp?: string },
  ) {
    return this.deviceService.registerCameraOrGet(body);
  }

  @Post('cameras')
  async createCamera(@Body() body: Partial<Camera>) {
    return this.deviceService.createCamera(body);
  }

  @Put('cameras/:id')
  async updateCamera(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() body: Partial<Camera>,
  ) {
    return this.deviceService.updateCamera(id, body);
  }

  @Delete('cameras/:id')
  async deleteCamera(@Param('id', ParseUUIDPipe) id: string) {
    await this.deviceService.deleteCamera(id);
    return { ok: true };
  }

  @Get('detections/:id/image')
  async getDetectionImage(@Param('id', ParseUUIDPipe) id: string): Promise<StreamableFile> {
    const detection = await this.deviceService.findDetectionById(id);
    if (!detection?.imagePath || !fs.existsSync(detection.imagePath)) {
      throw new NotFoundException('Image not found');
    }
    const ext = path.extname(detection.imagePath).toLowerCase();
    const type =
      ext === '.png' ? 'image/png' : ext === '.gif' ? 'image/gif' : ext === '.webp' ? 'image/webp' : 'image/jpeg';
    const stream = fs.createReadStream(detection.imagePath);
    return new StreamableFile(stream, { type });
  }

  @Get('detections')
  async getDetections(
    @Query('cameraId') cameraId?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
    @Query('archived') archived?: string,
    @Query('search') search?: string,
    @Query('sortBy') sortBy?: string,
    @Query('sortOrder') sortOrder?: string,
  ) {
    const archivedParam =
      archived === 'true' ? true : archived === 'false' ? false : undefined;
    const limitNum = limit ? parseInt(limit, 10) : 500;
    const offsetNum = offset ? parseInt(offset, 10) : 0;
    const safeLimit = Number.isFinite(limitNum) && limitNum > 0 ? Math.min(limitNum, 2000) : 500;
    const safeOffset = Number.isFinite(offsetNum) && offsetNum >= 0 ? offsetNum : 0;
    const allowedSortBy = ['timestamp', 'licensePlate', 'confidence', 'createdAt'];
    const safeSortBy = sortBy && allowedSortBy.includes(sortBy) ? sortBy : 'timestamp';
    const safeSortOrder = sortOrder === 'ASC' || sortOrder === 'DESC' ? sortOrder : 'DESC';
    return this.deviceService.findAllDetections(
      cameraId,
      safeLimit,
      safeOffset,
      archivedParam,
      search,
      safeSortBy,
      safeSortOrder,
    );
  }

  @Get('cameras/:id/detections')
  async getDetectionsByCamera(
    @Param('id', ParseUUIDPipe) id: string,
    @Query('limit') limit?: string,
  ) {
    return this.deviceService.findDetectionsByCameraId(
      id,
      limit ? parseInt(limit, 10) : 100,
    );
  }

  @Post('detections')
  async createDetection(@Body() body: Partial<Detection>) {
    return this.deviceService.createDetection(body);
  }

  @Patch('detections/image-path')
  async updateDetectionsImagePath(
    @Body() body: { cameraId: string; timestamp: string; imagePath: string },
  ) {
    return this.deviceService.updateDetectionsImagePath(
      body.cameraId,
      body.timestamp,
      body.imagePath,
    );
  }

  @Patch('detections/:id')
  async updateDetection(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() body: { archived?: boolean },
  ) {
    return this.deviceService.updateDetection(id, body);
  }

  @Get('camera-health')
  async getCameraHealth(
    @Query('cameraId') cameraId?: string,
    @Query('limit') limit?: string,
    @Query('from') from?: string,
    @Query('to') to?: string,
  ) {
    return this.deviceService.findAllCameraHealth(
      cameraId,
      limit ? parseInt(limit, 10) : 200,
      from,
      to,
    );
  }

  @Post('camera-health')
  async createCameraHealth(@Body() body: Partial<CameraHealth>) {
    return this.deviceService.createCameraHealth(body);
  }

  @Get('analytics')
  async getAnalytics(@Query('limit') limit?: string) {
    return this.deviceService.findAllAnalytics(
      limit ? parseInt(limit, 10) : 500,
    );
  }

  @Get('system-events')
  async getSystemEvents(@Query('limit') limit?: string) {
    return this.deviceService.findAllSystemEvents(
      limit ? parseInt(limit, 10) : 500,
    );
  }

  @Get('visualizations')
  async getVisualizations(@Query('limit') limit?: string) {
    return this.deviceService.findAllVisualizations(
      limit ? parseInt(limit, 10) : 500,
    );
  }

  @Get('analytics-events')
  async getAnalyticsEvents(@Query('limit') limit?: string) {
    return this.deviceService.findAllAnalyticsEvents(
      limit ? parseInt(limit, 10) : 500,
    );
  }
}
