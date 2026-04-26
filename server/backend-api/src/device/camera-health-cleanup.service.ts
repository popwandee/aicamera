import { Injectable } from '@nestjs/common';
import { Cron } from '@nestjs/schedule';
import { DeviceService } from './device.service';

const RETENTION_DAYS = 30;

@Injectable()
export class CameraHealthCleanupService {
  constructor(private readonly deviceService: DeviceService) {}

  @Cron('0 0 * * *')
  async handleDailyCleanup(): Promise<void> {
    const deleted = await this.deviceService.deleteCameraHealthOlderThan(RETENTION_DAYS);
    if (deleted > 0) {
      console.log(`[CameraHealthCleanup] Deleted ${deleted} camera_health rows older than ${RETENTION_DAYS} days`);
    }
  }
}
