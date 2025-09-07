import { Module } from '@nestjs/common';
import { ServeStaticModule } from '@nestjs/serve-static';
import { join } from 'path';
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { ConfigModule } from '@nestjs/config';
// import { CommunicationModule } from './communication/communication.module';
// import { SystemModule } from './system/system.module';
// import { AuthModule } from './auth/auth.module';
// import { DeviceRegistrationModule } from './device-registration/device-registration.module';
import { DeviceService } from './device/device.service';
import { SftpService } from './sftp/sftp.service';
import { DatabaseModule } from './database/database.module';
import { HealthModule } from './modules/health/health.module';
import { DetectionModule } from './modules/detection/detection.module';
import { CameraModule } from './modules/camera/camera.module';
import { AnalyticsModule } from './modules/analytics/analytics.module';
import { rateLimitConfig } from './config/rate-limit.config';
import { SpaController } from './controllers/spa.controller';

const GlobalConfigModule = ConfigModule.forRoot({ isGlobal: true }) as unknown as import('@nestjs/common').DynamicModule;

@Module({
  imports: [
    GlobalConfigModule,
    // Temporarily disable ThrottlerModule root to avoid duplicate nest type issues
    // ThrottlerModule.forRoot(rateLimitConfig),
    ServeStaticModule.forRoot({
      rootPath: join(process.cwd(), 'frontend', 'dist'),
      exclude: ['/api*'],
    }),
    DatabaseModule,
    HealthModule,
    DetectionModule,
    CameraModule,
    AnalyticsModule,
  ],
  controllers: [SpaController],
  providers: [
    DeviceService,
    SftpService,
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
  ],
})
export class AppModule {}
