import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  OnGatewayConnection,
  OnGatewayDisconnect,
  OnGatewayInit,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { Logger, WS_EVENTS, IDetectionRequest, ValidationUtil } from '@aicamera/shared';
import { DetectionService } from '../services/detection.service';
import { UseGuards, UsePipes, ValidationPipe } from '@nestjs/common';

@WebSocketGateway({
  cors: {
    origin: process.env.CORS_ORIGINS?.split(',') || ['http://localhost:8080'],
    credentials: true,
  },
  namespace: '/detection',
})
@UsePipes(new ValidationPipe())
export class DetectionGateway implements OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = Logger.create('Detection-Gateway');
  private connectedClients = new Map<string, { deviceId?: string; userType?: string }>();

  constructor(private readonly detectionService: DetectionService) {}

  afterInit(server: Server) {
    this.logger.info('Detection WebSocket Gateway initialized');
  }

  handleConnection(client: Socket) {
    const clientId = client.id;
    this.connectedClients.set(clientId, {});
    
    this.logger.info(`Client connected: ${clientId}`);
    
    // Send welcome message
    client.emit('connected', {
      message: 'Connected to AI Camera Detection Service',
      clientId,
      timestamp: new Date().toISOString(),
    });
  }

  handleDisconnect(client: Socket) {
    const clientId = client.id;
    const clientInfo = this.connectedClients.get(clientId);
    
    this.connectedClients.delete(clientId);
    
    this.logger.info(`Client disconnected: ${clientId}`, { clientInfo });
  }

  @SubscribeMessage(WS_EVENTS.DEVICE_REGISTER)
  async handleDeviceRegistration(
    @MessageBody() data: { deviceId: string; type?: string },
    @ConnectedSocket() client: Socket,
  ) {
    try {
      if (!ValidationUtil.isValidDeviceId(data.deviceId)) {
        client.emit('error', { message: 'Invalid device ID format' });
        return;
      }

      // Register the device connection
      this.connectedClients.set(client.id, {
        deviceId: data.deviceId,
        userType: 'device',
      });

      // Join device-specific room
      client.join(`device:${data.deviceId}`);

      this.logger.info(`Device registered: ${data.deviceId}`, { clientId: client.id });

      client.emit('device_registered', {
        success: true,
        deviceId: data.deviceId,
        message: 'Device registered successfully',
        timestamp: new Date().toISOString(),
      });

    } catch (error) {
      this.logger.error('Failed to register device', error);
      client.emit('error', { message: 'Device registration failed' });
    }
  }

  @SubscribeMessage(WS_EVENTS.DETECTION_NEW)
  async handleNewDetection(
    @MessageBody() detectionData: IDetectionRequest,
    @ConnectedSocket() client: Socket,
  ) {
    try {
      const clientInfo = this.connectedClients.get(client.id);
      
      if (!clientInfo?.deviceId) {
        client.emit('error', { message: 'Device not registered' });
        return;
      }

      // Ensure detection is from the registered device
      if (detectionData.deviceId !== clientInfo.deviceId) {
        client.emit('error', { message: 'Detection deviceId mismatch' });
        return;
      }

      // Store detection in database
      const detection = await this.detectionService.createDetection(detectionData);

      // Broadcast to dashboard clients
      this.server.emit(WS_EVENTS.DASHBOARD_DETECTION_UPDATE, {
        detection,
        deviceId: clientInfo.deviceId,
        timestamp: new Date().toISOString(),
      });

      // Send confirmation to device
      client.emit('detection_stored', {
        success: true,
        detectionId: detection.id,
        timestamp: new Date().toISOString(),
      });

      this.logger.info(`Detection received from device ${clientInfo.deviceId}`, {
        type: detection.type,
        confidence: detection.confidence,
      });

    } catch (error) {
      this.logger.error('Failed to handle detection', error);
      client.emit('error', { message: 'Failed to store detection' });
    }
  }

  @SubscribeMessage(WS_EVENTS.DETECTION_BULK)
  async handleBulkDetections(
    @MessageBody() data: { detections: IDetectionRequest[] },
    @ConnectedSocket() client: Socket,
  ) {
    try {
      const clientInfo = this.connectedClients.get(client.id);
      
      if (!clientInfo?.deviceId) {
        client.emit('error', { message: 'Device not registered' });
        return;
      }

      // Validate all detections are from the registered device
      for (const detection of data.detections) {
        if (detection.deviceId !== clientInfo.deviceId) {
          client.emit('error', { message: 'Detection deviceId mismatch in bulk data' });
          return;
        }
      }

      // Store all detections
      const detections = await this.detectionService.createBulkDetections(data.detections);

      // Broadcast to dashboard clients
      this.server.emit(WS_EVENTS.DASHBOARD_DETECTION_UPDATE, {
        detections,
        deviceId: clientInfo.deviceId,
        bulk: true,
        count: detections.length,
        timestamp: new Date().toISOString(),
      });

      // Send confirmation to device
      client.emit('bulk_detections_stored', {
        success: true,
        count: detections.length,
        detectionIds: detections.map(d => d.id),
        timestamp: new Date().toISOString(),
      });

      this.logger.info(`Bulk detections received from device ${clientInfo.deviceId}`, {
        count: detections.length,
      });

    } catch (error) {
      this.logger.error('Failed to handle bulk detections', error);
      client.emit('error', { message: 'Failed to store bulk detections' });
    }
  }

  @SubscribeMessage('join_dashboard')
  async handleDashboardJoin(
    @MessageBody() data: { userType: string },
    @ConnectedSocket() client: Socket,
  ) {
    try {
      // Register dashboard client
      this.connectedClients.set(client.id, {
        userType: 'dashboard',
      });

      // Join dashboard room for broadcasts
      client.join('dashboard');

      // Send recent detections
      const recentDetections = await this.detectionService.getRecentDetections(10);
      client.emit('recent_detections', {
        detections: recentDetections,
        timestamp: new Date().toISOString(),
      });

      this.logger.info(`Dashboard client joined: ${client.id}`);

      client.emit('dashboard_joined', {
        success: true,
        message: 'Joined dashboard successfully',
        timestamp: new Date().toISOString(),
      });

    } catch (error) {
      this.logger.error('Failed to handle dashboard join', error);
      client.emit('error', { message: 'Failed to join dashboard' });
    }
  }

  // Utility methods for broadcasting from other services
  broadcastToDevice(deviceId: string, event: string, data: any) {
    this.server.to(`device:${deviceId}`).emit(event, {
      ...data,
      timestamp: new Date().toISOString(),
    });
  }

  broadcastToDashboard(event: string, data: any) {
    this.server.to('dashboard').emit(event, {
      ...data,
      timestamp: new Date().toISOString(),
    });
  }

  broadcastToAll(event: string, data: any) {
    this.server.emit(event, {
      ...data,
      timestamp: new Date().toISOString(),
    });
  }

  getConnectionStats() {
    const deviceConnections = Array.from(this.connectedClients.values())
      .filter(client => client.userType === 'device').length;
    
    const dashboardConnections = Array.from(this.connectedClients.values())
      .filter(client => client.userType === 'dashboard').length;

    return {
      total: this.connectedClients.size,
      devices: deviceConnections,
      dashboards: dashboardConnections,
      timestamp: new Date().toISOString(),
    };
  }
}