import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { DeviceModule } from './modules/device.module';
import { HealthModule } from './modules/health.module';
import { DatabaseModule } from './modules/database.module';
import { MqttClientModule } from './modules/mqtt-client.module';
import { RedisModule } from './modules/redis.module';

@Module({
  imports: [
    // Configuration
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env.local', '.env'],
    }),

    // Rate limiting
    ThrottlerModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (config: ConfigService) => [
        {
          name: 'short',
          ttl: parseInt(config.get('RATE_LIMIT_WINDOW_MS', '60000')),
          limit: parseInt(config.get('RATE_LIMIT_MAX', '10')),
        },
        {
          name: 'long',
          ttl: parseInt(config.get('RATE_LIMIT_WINDOW_MS', '900000')), // 15 minutes
          limit: parseInt(config.get('RATE_LIMIT_MAX', '100')),
        },
      ],
    }),

    // Core modules
    DatabaseModule,
    RedisModule,
    MqttClientModule,

    // Feature modules
    DeviceModule,
    HealthModule,
  ],
})
export class AppModule {}