export interface IEdgeDevice {
  id: string;
  deviceId: string;
  name: string;
  type: EdgeDeviceType;
  status: DeviceStatus;
  ipAddress?: string;
  macAddress?: string;
  version?: string;
  capabilities?: Record<string, any>;
  location?: string;
  latitude?: number;
  longitude?: number;
  lastSeen?: Date;
  lastHeartbeat?: Date;
  metadata?: Record<string, any>;
  createdAt: Date;
  updatedAt: Date;
}

export interface IDeviceRegistration {
  deviceId: string;
  name: string;
  type: EdgeDeviceType;
  capabilities?: Record<string, any>;
  location?: string;
  latitude?: number;
  longitude?: number;
  metadata?: Record<string, any>;
}

export interface IDeviceHeartbeat {
  deviceId: string;
  timestamp: Date;
  status: DeviceStatus;
  systemInfo?: {
    cpuUsage?: number;
    memoryUsage?: number;
    diskUsage?: number;
    temperature?: number;
    uptime?: number;
  };
  networkInfo?: {
    ipAddress?: string;
    macAddress?: string;
    signalStrength?: number;
  };
}

export interface IDeviceLog {
  id: string;
  deviceId: string;
  level: LogLevel;
  message: string;
  data?: Record<string, any>;
  createdAt: Date;
}

export enum EdgeDeviceType {
  CAMERA = 'CAMERA',
  SENSOR = 'SENSOR',
  GATEWAY = 'GATEWAY',
  OTHER = 'OTHER',
}

export enum DeviceStatus {
  ONLINE = 'ONLINE',
  OFFLINE = 'OFFLINE',
  CONNECTING = 'CONNECTING',
  ERROR = 'ERROR',
  MAINTENANCE = 'MAINTENANCE',
}

export enum LogLevel {
  ERROR = 'ERROR',
  WARN = 'WARN',
  INFO = 'INFO',
  DEBUG = 'DEBUG',
}