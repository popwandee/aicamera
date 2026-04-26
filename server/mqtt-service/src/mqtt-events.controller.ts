import { Controller } from '@nestjs/common';
import { Ctx, MessagePattern, MqttContext, Payload } from '@nestjs/microservices';
import { MqttEventsService } from './mqtt-events.service';

/**
 * Subscribe to MQTT topics from Edge Client (ตาม docs/server/communication-services.md).
 * รับข้อมูลแล้วบันทึกลง log เพื่อตรวจสอบและเตรียมเขียนลง DB ในอนาคต
 */
@Controller()
export class MqttEventsController {
  constructor(private readonly mqttEventsService: MqttEventsService) {}

  @MessagePattern('camera/+/status')
  handleCameraStatus(@Payload() data: unknown, @Ctx() context: MqttContext) {
    const topic = context.getTopic();
    this.mqttEventsService.logReceived(topic, data);
    this.mqttEventsService.persistCameraHealthToBackend(topic, data).catch(() => {});
    return { received: true };
  }

  @MessagePattern('camera/+/health')
  handleCameraHealth(@Payload() data: unknown, @Ctx() context: MqttContext) {
    const topic = context.getTopic();
    this.mqttEventsService.logReceived(topic, data);
    this.mqttEventsService.persistCameraHealthToBackend(topic, data).catch(() => {});
    return { received: true };
  }

  @MessagePattern('camera/+/detections')
  handleCameraDetections(@Payload() data: unknown, @Ctx() context: MqttContext) {
    const topic = context.getTopic();
    this.mqttEventsService.logReceived(topic, data);
    return { received: true };
  }

  @MessagePattern('system/events')
  handleSystemEvents(@Payload() data: unknown, @Ctx() context: MqttContext) {
    const topic = context.getTopic();
    this.mqttEventsService.logReceived(topic, data);
    return { received: true };
  }

  @MessagePattern('system/health')
  handleSystemHealth(@Payload() data: unknown, @Ctx() context: MqttContext) {
    const topic = context.getTopic();
    this.mqttEventsService.logReceived(topic, data);
    return { received: true };
  }
}
