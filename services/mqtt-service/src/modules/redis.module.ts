import { Global, Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createClient, RedisClientType } from 'redis';
import { Logger } from '@aicamera/shared';

@Global()
@Module({
  providers: [
    {
      provide: 'REDIS_CLIENT',
      useFactory: async (config: ConfigService): Promise<RedisClientType> => {
        const logger = Logger.create('Redis');
        const redisUrl = config.get('REDIS_URL', 'redis://localhost:6379');

        const client = createClient({
          url: redisUrl,
          socket: {
            reconnectStrategy: (retries) => {
              logger.warn(`Redis reconnection attempt ${retries}`);
              return Math.min(retries * 50, 1000);
            },
          },
        });

        client.on('error', (error) => {
          logger.error('Redis connection error', error);
        });

        client.on('connect', () => {
          logger.info('Connected to Redis');
        });

        client.on('disconnect', () => {
          logger.warn('Disconnected from Redis');
        });

        await client.connect();
        return client;
      },
      inject: [ConfigService],
    },
  ],
  exports: ['REDIS_CLIENT'],
})
export class RedisModule {}