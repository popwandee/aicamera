import { Module } from '@nestjs/common';
import { DetectionGateway } from '../gateways/detection.gateway';
import { DetectionService } from '../services/detection.service';

@Module({
  providers: [DetectionGateway, DetectionService],
  exports: [DetectionGateway],
})
export class WebSocketModule {}