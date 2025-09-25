// Generic response types
export type ServiceResponse<T = any> = {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
};

// Pagination types
export type PaginatedResponse<T> = {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
};

// Filter types
export type SortOrder = 'asc' | 'desc';

export type BaseFilter = {
  search?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortOrder?: SortOrder;
};

// Event types
export type EventType = 'device' | 'detection' | 'file' | 'user' | 'system';

export type EventPayload<T = any> = {
  type: EventType;
  action: string;
  data: T;
  timestamp: Date;
  source?: string;
};

// Configuration types
export type ServiceConfig = {
  port: number;
  host: string;
  environment: 'development' | 'production' | 'test';
  database: {
    url: string;
    maxConnections?: number;
    timeout?: number;
  };
  redis?: {
    url: string;
    keyPrefix?: string;
  };
  jwt: {
    secret: string;
    expiresIn: string;
  };
  logging: {
    level: 'error' | 'warn' | 'info' | 'debug';
  };
};

// Microservice communication types
export type ServiceMessage<T = any> = {
  id: string;
  service: string;
  action: string;
  payload: T;
  timestamp: Date;
  replyTo?: string;
};

// Health check types
export type HealthStatus = {
  status: 'healthy' | 'unhealthy' | 'degraded';
  timestamp: Date;
  version: string;
  uptime: number;
  dependencies: {
    [key: string]: {
      status: 'up' | 'down';
      responseTime?: number;
      error?: string;
    };
  };
};

// Statistics types
export type DeviceStatistics = {
  totalDevices: number;
  onlineDevices: number;
  offlineDevices: number;
  devicesByType: Record<string, number>;
  devicesByStatus: Record<string, number>;
};

export type DetectionStatistics = {
  totalDetections: number;
  detectionsByType: Record<string, number>;
  detectionsByDevice: Record<string, number>;
  detectionsToday: number;
  detectionsThisWeek: number;
  detectionsThisMonth: number;
  averageConfidence: number;
};

export type FileStatistics = {
  totalFiles: number;
  totalSize: number;
  filesByDevice: Record<string, number>;
  filesByStatus: Record<string, number>;
  filesByType: Record<string, number>;
  storageUsed: number;
  storageAvailable: number;
};

// Error types
export type ServiceError = {
  code: string;
  message: string;
  details?: any;
  timestamp: Date;
  service?: string;
};

// Utility types
export type Nullable<T> = T | null;
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type RequiredFields<T, K extends keyof T> = T & Required<Pick<T, K>>;

// Environment variables type
export type Environment = {
  NODE_ENV: 'development' | 'production' | 'test';
  PORT: number;
  DATABASE_URL: string;
  REDIS_URL?: string;
  MQTT_URL?: string;
  JWT_SECRET: string;
  JWT_EXPIRES_IN: string;
  LOG_LEVEL: 'error' | 'warn' | 'info' | 'debug';
  CORS_ORIGINS: string;
  MAX_FILE_SIZE: number;
  STORAGE_PATH: string;
};

// API types
export type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export type APIEndpoint = {
  method: HTTPMethod;
  path: string;
  description: string;
  requiresAuth: boolean;
  roles?: string[];
};

// Queue types (for future message queue implementation)
export type QueueJob<T = any> = {
  id: string;
  type: string;
  payload: T;
  priority: number;
  attempts: number;
  maxAttempts: number;
  createdAt: Date;
  processedAt?: Date;
  error?: string;
};