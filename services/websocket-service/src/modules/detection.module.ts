import { Module } from '@nestjs/common';
import { DetectionGateway } from '../gateways/detection.gateway';
import { DetectionService } from '../services/detection.service';
import { DetectionController } from '../controllers/detection.controller';

@Module({
  controllers: [DetectionController],
  providers: [DetectionGateway, DetectionService],
  exports: [DetectionGateway, DetectionService],
})
export class DetectionModule {}