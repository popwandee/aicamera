import { Global, Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaClient } from '../../../database/generated/client';

@Global()
@Module({
  providers: [
    {
      provide: 'PRISMA_CLIENT',
      useFactory: async (config: ConfigService) => {
        const prisma = new PrismaClient({
          datasources: {
            db: {
              url: config.get('DATABASE_URL'),
            },
          },
          log: config.get('NODE_ENV') === 'development' ? ['query', 'info', 'warn', 'error'] : ['warn', 'error'],
        });

        await prisma.$connect();
        return prisma;
      },
      inject: [ConfigService],
    },
  ],
  exports: ['PRISMA_CLIENT'],
})
export class DatabaseModule {}