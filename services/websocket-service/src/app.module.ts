import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { DetectionModule } from './modules/detection.module';
import { WebSocketModule } from './modules/websocket.module';
import { DatabaseModule } from './modules/database.module';
import { RedisModule } from './modules/redis.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env.local', '.env'],
    }),
    DatabaseModule,
    RedisModule,
    WebSocketModule,
    DetectionModule,
  ],
})
export class AppModule {}