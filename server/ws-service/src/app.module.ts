import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { EventsGateway } from './events.gateway';
import { StorageService } from './storage.service';
import { BackendApiService } from './backend-api.service';

@Module({
  imports: [],
  controllers: [AppController],
  providers: [AppService, EventsGateway, StorageService, BackendApiService],
})
export class AppModule {}
