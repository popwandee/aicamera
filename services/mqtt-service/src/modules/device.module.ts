import { Module } from '@nestjs/common';
import { DeviceController } from '../controllers/device.controller';
import { DeviceService } from '../services/device.service';
import { MqttClientService } from '../services/mqtt-client.service';

@Module({
  controllers: [DeviceController],
  providers: [DeviceService, MqttClientService],
  exports: [DeviceService, MqttClientService],
})
export class DeviceModule {}