import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { StorageService } from './storage.service';
import { BackendApiService, type DetectionResultContent } from './backend-api.service';

@WebSocketGateway({ cors: { origin: '*' }, path: '/ws/' })
export class EventsGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(EventsGateway.name);
  private readonly cameraIdToUuid = new Map<string, string>();

  constructor(
    private readonly storageService: StorageService,
    private readonly backendApi: BackendApiService,
  ) {}

  handleConnection(client: any) {
    this.logger.log(`Client connected: ${client.id}`);
  }

  handleDisconnect(client: any) {
    this.logger.log(`Client disconnected: ${client.id}`);
  }

  private async ensureCameraUuid(
    cameraId: string,
    checkpointId?: string,
  ): Promise<string> {
    let uuid = this.cameraIdToUuid.get(cameraId);
    if (uuid) return uuid;
    const camera = await this.backendApi.registerCamera({
      camera_id: cameraId,
      checkpoint_id: checkpointId || cameraId,
    });
    this.cameraIdToUuid.set(cameraId, camera.id);
    return camera.id;
  }

  private parseTimestampFromFilename(filename: string): string | null {
    const match = /detection_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.jpg/i.exec(
      filename || '',
    );
    if (!match) return null;
    const [, y, m, d, h, min, s] = match;
    return `${y}-${m}-${d}T${h}:${min}:${s}.000000`;
  }

  @SubscribeMessage('camera_register')
  async handleCameraRegister(
    @MessageBody()
    payload: { camera_id: string; checkpoint_id: string; timestamp?: string },
    @ConnectedSocket() client: any,
  ) {
    try {
      const camera = await this.backendApi.registerCamera({
        camera_id: payload.camera_id,
        checkpoint_id: payload.checkpoint_id,
        timestamp: payload.timestamp,
      });
      this.cameraIdToUuid.set(payload.camera_id, camera.id);
      this.logger.log(`Camera registered: ${payload.camera_id} -> ${camera.id}`);
      client.emit('camera_registered', { camera_id: payload.camera_id, id: camera.id });
    } catch (error: any) {
      this.logger.error(`Camera register failed: ${error?.message}`);
      client.emit('message_error', { success: false, error: error?.message });
    }
  }

  @SubscribeMessage('image')
  async handleImage(
    @MessageBody() data: { data: string; filename?: string; camera_id?: string },
    @ConnectedSocket() client: any,
  ) {
    try {
      const filePath = await this.storageService.saveImage(
        data.data,
        data.filename,
        data.camera_id,
      );
      this.logger.log(`Image saved: ${filePath}`);

      if (data.camera_id) {
        const cameraUuid = await this.ensureCameraUuid(data.camera_id);
        const timestampIso = this.parseTimestampFromFilename(data.filename || '');
        if (timestampIso) {
          const { affected } = await this.backendApi.updateDetectionsImagePath(
            cameraUuid,
            timestampIso,
            filePath,
          );
          if (affected > 0) {
            this.logger.log(`Updated ${affected} detection(s) with image_path`);
          }
        }
      }

      client.emit('image_saved', { path: filePath, success: true });
    } catch (error: any) {
      this.logger.error(`Failed to save image: ${error?.message}`);
      client.emit('image_error', { success: false, error: error?.message });
    }
  }

  @SubscribeMessage('message')
  async handleMessage(
    @MessageBody() data: string | Record<string, any>,
    @ConnectedSocket() client: any,
  ) {
    try {
      const raw = typeof data === 'string' ? data : data?.content ?? data;
      const content = typeof raw === 'object' ? raw : JSON.parse(String(raw));
      await this.storageService.saveMessage(
        typeof raw === 'string' ? raw : JSON.stringify(raw),
      );

      if (content?.type !== 'detection_result') {
        client.emit('message_saved', { success: true });
        return;
      }

      const cameraId = (data as Record<string, unknown>)?.camera_id ?? content.aicamera_id;
      if (!cameraId) {
        client.emit('message_error', { success: false, error: 'Missing camera_id' });
        return;
      }

      const cameraUuid = await this.ensureCameraUuid(
        String(cameraId),
        content.checkpoint_id,
      );
      const detections = await this.backendApi.createDetections(
        cameraUuid,
        content as DetectionResultContent,
      );
      const recordId = detections.length > 0 ? detections[0].id : null;
      this.logger.log(
        `Message (detection_result) saved from client ${client.id}, ${detections.length} detection(s)`,
      );
      client.emit('message_saved', {
        record_id: recordId,
        message: 'message_saved',
        success: true,
      });
    } catch (error: any) {
      this.logger.error(`Failed to save message: ${error?.message}`);
      client.emit('message_error', { success: false, error: error?.message });
    }
  }

  @SubscribeMessage('health_status')
  async handleHealthStatus(
    @MessageBody()
    payload: {
      type: string;
      aicamera_id: string;
      checkpoint_id: string;
      timestamp?: string;
      component: string;
      status: string;
      message: string;
      details?: string;
      created_at?: string;
    },
    @ConnectedSocket() client: any,
  ) {
    try {
      const cameraId = payload.aicamera_id;
      const cameraUuid = await this.ensureCameraUuid(
        cameraId,
        payload.checkpoint_id,
      );
      await this.backendApi.createCameraHealth(cameraUuid, payload);
      this.logger.log(`Health status saved: ${cameraId} ${payload.status}`);
      client.emit('health_saved', { success: true });
    } catch (error: any) {
      this.logger.error(`Health status save failed: ${error?.message}`);
      client.emit('message_error', { success: false, error: error?.message });
    }
  }
}
