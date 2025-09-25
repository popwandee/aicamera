import { Global, Module, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as mqtt from 'mqtt';
import { Logger } from '@aicamera/shared';
import { MqttClientService } from '../services/mqtt-client.service';

@Global()
@Module({
  providers: [
    {
      provide: 'MQTT_CLIENT',
      useFactory: (config: ConfigService) => {
        const logger = Logger.create('MQTT-Client');
        const mqttUrl = config.get('MQTT_URL', 'mqtt://localhost:1883');

        const client = mqtt.connect(mqttUrl, {
          clientId: `mqtt-service-${Date.now()}`,
          clean: true,
          keepalive: 60,
          reconnectPeriod: 1000,
          connectTimeout: 30 * 1000,
        });

        client.on('connect', () => {
          logger.info('Connected to MQTT broker');
        });

        client.on('error', (error) => {
          logger.error('MQTT client error', error);
        });

        client.on('offline', () => {
          logger.warn('MQTT client went offline');
        });

        client.on('reconnect', () => {
          logger.info('MQTT client reconnecting');
        });

        client.on('close', () => {
          logger.warn('MQTT connection closed');
        });

        return client;
      },
      inject: [ConfigService],
    },
    MqttClientService,
  ],
  exports: ['MQTT_CLIENT', MqttClientService],
})
export class MqttClientModule implements OnModuleInit, OnModuleDestroy {
  constructor(private readonly mqttClientService: MqttClientService) {}

  async onModuleInit() {
    await this.mqttClientService.subscribeToDeviceTopics();
  }

  async onModuleDestroy() {
    await this.mqttClientService.disconnect();
  }
}