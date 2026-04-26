import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { BackendApiService } from './backend-api.service';
import { MqttEventsController } from './mqtt-events.controller';
import { MqttEventsService } from './mqtt-events.service';

@Module({
  imports: [],
  controllers: [AppController, MqttEventsController],
  providers: [AppService, MqttEventsService, BackendApiService],
})
export class AppModule {}
