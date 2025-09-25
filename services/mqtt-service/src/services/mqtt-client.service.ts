import { Injectable, Inject, OnModuleDestroy } from '@nestjs/common';
import { MqttClient } from 'mqtt';
import { 
  Logger, 
  MQTT_TOPICS, 
  IDeviceRegistration, 
  IDeviceHeartbeat, 
  IDeviceLog,
  DeviceStatus,
  LogLevel 
} from '@aicamera/shared';
import { DeviceService } from './device.service';

@Injectable()
export class MqttClientService implements OnModuleDestroy {
  private readonly logger = Logger.create('MQTT-Client-Service');

  constructor(
    @Inject('MQTT_CLIENT') private readonly mqttClient: MqttClient,
    private readonly deviceService: DeviceService,
  ) {}

  async onModuleDestroy() {
    await this.disconnect();
  }

  async subscribeToDeviceTopics(): Promise<void> {
    try {
      // Subscribe to device registration topic
      await this.subscribe(MQTT_TOPICS.DEVICE.REGISTER, (topic, message) => 
        this.handleDeviceRegistration(topic, message)
      );

      // Subscribe to device heartbeat topic
      await this.subscribe(MQTT_TOPICS.DEVICE.HEARTBEAT, (topic, message) => 
        this.handleDeviceHeartbeat(topic, message)
      );

      // Subscribe to device status topic
      await this.subscribe(MQTT_TOPICS.DEVICE.STATUS, (topic, message) => 
        this.handleDeviceStatus(topic, message)
      );

      // Subscribe to device log topic
      await this.subscribe(MQTT_TOPICS.DEVICE.LOG, (topic, message) => 
        this.handleDeviceLog(topic, message)
      );

      this.logger.info('Subscribed to all device MQTT topics');
    } catch (error) {
      this.logger.error('Failed to subscribe to MQTT topics', error);
      throw error;
    }
  }

  private async subscribe(
    topicPattern: string, 
    handler: (topic: string, message: any) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      this.mqttClient.subscribe(topicPattern, (error) => {
        if (error) {
          this.logger.error(`Failed to subscribe to ${topicPattern}`, error);
          reject(error);
        } else {
          this.logger.debug(`Subscribed to ${topicPattern}`);
          resolve();
        }
      });

      this.mqttClient.on('message', (topic, payload) => {
        if (this.topicMatches(topic, topicPattern)) {
          try {
            const message = JSON.parse(payload.toString());
            handler(topic, message);
          } catch (parseError) {
            this.logger.error(`Failed to parse MQTT message from ${topic}`, parseError);
          }
        }
      });
    });
  }

  private topicMatches(topic: string, pattern: string): boolean {
    const topicParts = topic.split('/');
    const patternParts = pattern.split('/');

    if (topicParts.length !== patternParts.length) {
      return false;
    }

    return patternParts.every((part, index) => 
      part === '+' || part === topicParts[index]
    );
  }

  private extractDeviceIdFromTopic(topic: string): string | null {
    // Topic format: aicamera/device/{deviceId}/action
    const parts = topic.split('/');
    return parts.length >= 3 ? parts[2] : null;
  }

  private async handleDeviceRegistration(topic: string, message: any): Promise<void> {
    try {
      const deviceId = this.extractDeviceIdFromTopic(topic);
      if (!deviceId) {
        this.logger.warn(`Invalid device registration topic: ${topic}`);
        return;
      }

      this.logger.info(`Device registration received from ${deviceId}`, message);

      const deviceData: IDeviceRegistration = {
        deviceId,
        name: message.name || `Device ${deviceId}`,
        type: message.type || 'OTHER',
        capabilities: message.capabilities || {},
        location: message.location,
        latitude: message.latitude,
        longitude: message.longitude,
        metadata: message.metadata || {},
      };

      await this.deviceService.registerDevice(deviceData);

      // Send configuration back to device
      await this.sendDeviceConfig(deviceId);
      
      this.logger.info(`Device registered successfully: ${deviceId}`);
    } catch (error) {
      this.logger.error(`Failed to handle device registration from topic ${topic}`, error);
    }
  }

  private async handleDeviceHeartbeat(topic: string, message: any): Promise<void> {
    try {
      const deviceId = this.extractDeviceIdFromTopic(topic);
      if (!deviceId) {
        this.logger.warn(`Invalid device heartbeat topic: ${topic}`);
        return;
      }

      const heartbeatData: IDeviceHeartbeat = {
        deviceId,
        timestamp: new Date(message.timestamp || Date.now()),
        status: message.status || DeviceStatus.ONLINE,
        systemInfo: message.systemInfo,
        networkInfo: message.networkInfo,
      };

      await this.deviceService.updateHeartbeat(heartbeatData);

      this.logger.debug(`Heartbeat received from device ${deviceId}`);
    } catch (error) {
      this.logger.error(`Failed to handle heartbeat from topic ${topic}`, error);
    }
  }

  private async handleDeviceStatus(topic: string, message: any): Promise<void> {
    try {
      const deviceId = this.extractDeviceIdFromTopic(topic);
      if (!deviceId) {
        this.logger.warn(`Invalid device status topic: ${topic}`);
        return;
      }

      await this.deviceService.updateDeviceStatus(
        deviceId, 
        message.status || DeviceStatus.ONLINE,
        message.metadata
      );

      this.logger.info(`Device status updated: ${deviceId} -> ${message.status}`);
    } catch (error) {
      this.logger.error(`Failed to handle device status from topic ${topic}`, error);
    }
  }

  private async handleDeviceLog(topic: string, message: any): Promise<void> {
    try {
      const deviceId = this.extractDeviceIdFromTopic(topic);
      if (!deviceId) {
        this.logger.warn(`Invalid device log topic: ${topic}`);
        return;
      }

      const logData: IDeviceLog = {
        id: '', // Will be generated by the service
        deviceId,
        level: message.level || LogLevel.INFO,
        message: message.message || 'No message',
        data: message.data,
        createdAt: new Date(message.timestamp || Date.now()),
      };

      await this.deviceService.createDeviceLog(logData);

      this.logger.debug(`Log received from device ${deviceId}: ${message.message}`);
    } catch (error) {
      this.logger.error(`Failed to handle device log from topic ${topic}`, error);
    }
  }

  async sendDeviceConfig(deviceId: string): Promise<void> {
    try {
      const config = await this.deviceService.getDeviceConfig(deviceId);
      const topic = MQTT_TOPICS.DEVICE.CONFIG.replace('+', deviceId);
      
      await this.publish(topic, config);
      this.logger.debug(`Configuration sent to device ${deviceId}`);
    } catch (error) {
      this.logger.error(`Failed to send config to device ${deviceId}`, error);
    }
  }

  async broadcastSystemMessage(message: any): Promise<void> {
    try {
      await this.publish(MQTT_TOPICS.SYSTEM.BROADCAST, message);
      this.logger.info('System message broadcasted to all devices');
    } catch (error) {
      this.logger.error('Failed to broadcast system message', error);
    }
  }

  async sendSystemAlert(alert: any): Promise<void> {
    try {
      await this.publish(MQTT_TOPICS.SYSTEM.ALERT, alert);
      this.logger.info('System alert sent to all devices');
    } catch (error) {
      this.logger.error('Failed to send system alert', error);
    }
  }

  private async publish(topic: string, message: any, qos: 0 | 1 | 2 = 1): Promise<void> {
    return new Promise((resolve, reject) => {
      this.mqttClient.publish(
        topic, 
        JSON.stringify(message), 
        { qos, retain: false },
        (error) => {
          if (error) {
            reject(error);
          } else {
            resolve();
          }
        }
      );
    });
  }

  async disconnect(): Promise<void> {
    return new Promise((resolve) => {
      this.mqttClient.end(true, () => {
        this.logger.info('MQTT client disconnected');
        resolve();
      });
    });
  }

  isConnected(): boolean {
    return this.mqttClient.connected;
  }

  getClientInfo(): any {
    return {
      connected: this.mqttClient.connected,
      reconnecting: this.mqttClient.reconnecting,
      clientId: this.mqttClient.options.clientId,
    };
  }
}