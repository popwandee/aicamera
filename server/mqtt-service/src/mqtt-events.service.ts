import { Injectable } from '@nestjs/common';
import * as fs from 'fs';
import * as path from 'path';
import { BackendApiService, MqttHealthPayload } from './backend-api.service';

const LOG_FILE = process.env.MQTT_RECEIVE_LOG ?? path.join(process.cwd(), '..', 'mqtt_receive.log');

@Injectable()
export class MqttEventsService {
  constructor(private readonly backendApi: BackendApiService) {}

  logReceived(topic: string, data: unknown): void {
    const line = `[${new Date().toISOString()}] ${topic} ${JSON.stringify(data)}\n`;
    try {
      fs.appendFileSync(LOG_FILE, line);
    } catch (err) {
      console.error('mqtt-events: failed to write log', err);
    }
  }

  /** Persist camera/+/health and camera/+/status to backend (cameras + camera_health). */
  async persistCameraHealthToBackend(topic: string, data: unknown): Promise<void> {
    const parts = topic.split('/');
    const cameraIdFromTopic = parts.length >= 2 ? parts[1] : '';
    let payload: MqttHealthPayload = {};
    if (typeof data === 'object' && data !== null) {
      payload = data as MqttHealthPayload;
    } else if (typeof data === 'string') {
      try {
        payload = JSON.parse(data) as MqttHealthPayload;
      } catch {
        return;
      }
    }
    const camera_id = payload.camera_id || cameraIdFromTopic;
    if (!camera_id) return;

    try {
      const camera = await this.backendApi.registerCamera({
        camera_id,
        checkpoint_id: payload.checkpoint_id,
        timestamp: payload.timestamp,
      });
      await this.backendApi.createCameraHealth(camera.id, { ...payload, camera_id });
    } catch (err) {
      console.error('mqtt-events: persist to backend failed', topic, err);
    }
  }
}
