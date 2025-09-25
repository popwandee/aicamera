import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { MulterModule } from '@nestjs/platform-express';
import { FileModule } from './modules/file.module';
import { DatabaseModule } from './modules/database.module';
import { RedisModule } from './modules/redis.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env.local', '.env'],
    }),
    MulterModule.register({
      dest: './storage/uploads',
    }),
    DatabaseModule,
    RedisModule,
    FileModule,
  ],
})
export class AppModule {}