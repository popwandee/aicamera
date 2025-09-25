export interface IMqttMessage {
  topic: string;
  payload: any;
  qos?: 0 | 1 | 2;
  retain?: boolean;
  timestamp?: Date;
}

export interface IMqttConfig {
  host: string;
  port: number;
  clientId: string;
  username?: string;
  password?: string;
  keepalive?: number;
  reconnectPeriod?: number;
  connectTimeout?: number;
}

export interface IWebSocketMessage {
  event: string;
  data: any;
  timestamp?: Date;
  deviceId?: string;
}

export interface IWebSocketConnection {
  id: string;
  deviceId?: string;
  userId?: string;
  connected: boolean;
  connectedAt: Date;
  lastActivity: Date;
  metadata?: Record<string, any>;
}

// MQTT Topics
export const MQTT_TOPICS = {
  DEVICE: {
    REGISTER: 'aicamera/device/+/register',
    HEARTBEAT: 'aicamera/device/+/heartbeat',
    STATUS: 'aicamera/device/+/status',
    LOG: 'aicamera/device/+/log',
    CONFIG: 'aicamera/device/+/config',
  },
  DETECTION: {
    NEW: 'aicamera/detection/+/new',
    BULK: 'aicamera/detection/+/bulk',
  },
  FILE: {
    UPLOAD_REQUEST: 'aicamera/file/+/upload_request',
    UPLOAD_STATUS: 'aicamera/file/+/upload_status',
    TRANSFER_COMPLETE: 'aicamera/file/+/transfer_complete',
  },
  SYSTEM: {
    BROADCAST: 'aicamera/system/broadcast',
    ALERT: 'aicamera/system/alert',
    CONFIG_UPDATE: 'aicamera/system/config_update',
  },
} as const;

// WebSocket Events
export const WS_EVENTS = {
  // Connection events
  CONNECTION: 'connection',
  DISCONNECT: 'disconnect',
  
  // Device events
  DEVICE_REGISTER: 'device_register',
  DEVICE_HEARTBEAT: 'device_heartbeat',
  DEVICE_STATUS_UPDATE: 'device_status_update',
  
  // Detection events
  DETECTION_NEW: 'detection_new',
  DETECTION_BULK: 'detection_bulk',
  
  // File events
  FILE_UPLOAD_START: 'file_upload_start',
  FILE_UPLOAD_PROGRESS: 'file_upload_progress',
  FILE_UPLOAD_COMPLETE: 'file_upload_complete',
  FILE_UPLOAD_ERROR: 'file_upload_error',
  
  // System events
  SYSTEM_ALERT: 'system_alert',
  SYSTEM_CONFIG_UPDATE: 'system_config_update',
  
  // Dashboard events
  DASHBOARD_STATS_UPDATE: 'dashboard_stats_update',
  DASHBOARD_DEVICE_UPDATE: 'dashboard_device_update',
  DASHBOARD_DETECTION_UPDATE: 'dashboard_detection_update',
} as const;

export interface ISystemAlert {
  id: string;
  type: AlertType;
  title: string;
  message: string;
  severity: AlertSeverity;
  deviceId?: string;
  data?: Record<string, any>;
  createdAt: Date;
  acknowledgedAt?: Date;
  acknowledgedBy?: string;
}

export enum AlertType {
  DEVICE_OFFLINE = 'DEVICE_OFFLINE',
  DEVICE_ERROR = 'DEVICE_ERROR',
  STORAGE_FULL = 'STORAGE_FULL',
  HIGH_DETECTION_RATE = 'HIGH_DETECTION_RATE',
  NETWORK_ERROR = 'NETWORK_ERROR',
  SYSTEM_ERROR = 'SYSTEM_ERROR',
}

export enum AlertSeverity {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}