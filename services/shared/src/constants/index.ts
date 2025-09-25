// Service Ports
export const SERVICE_PORTS = {
  API_GATEWAY: 3000,
  MQTT_SERVICE: 3001,
  WEBSOCKET_SERVICE: 3002,
  FILE_SERVICE: 3003,
} as const;

// Database
export const DATABASE_CONFIG = {
  DEFAULT_PAGE_SIZE: 10,
  MAX_PAGE_SIZE: 100,
  CONNECTION_TIMEOUT: 5000,
  QUERY_TIMEOUT: 30000,
} as const;

// File Storage
export const FILE_CONFIG = {
  MAX_FILE_SIZE: 50 * 1024 * 1024, // 50MB
  ALLOWED_IMAGE_TYPES: [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
  ],
  THUMBNAIL_SIZE: { width: 200, height: 200 },
  PREVIEW_SIZE: { width: 800, height: 600 },
  STORAGE_PATH: './storage',
  TEMP_PATH: './storage/temp',
  THUMBNAILS_PATH: './storage/thumbnails',
  PREVIEWS_PATH: './storage/previews',
} as const;

// MQTT Configuration
export const MQTT_CONFIG = {
  KEEP_ALIVE: 60,
  RECONNECT_PERIOD: 1000,
  CONNECT_TIMEOUT: 30000,
  QOS_LEVELS: {
    AT_MOST_ONCE: 0,
    AT_LEAST_ONCE: 1,
    EXACTLY_ONCE: 2,
  },
} as const;

// WebSocket Configuration
export const WS_CONFIG = {
  HEARTBEAT_INTERVAL: 30000, // 30 seconds
  CONNECTION_TIMEOUT: 5000,
  MAX_CONNECTIONS_PER_DEVICE: 3,
  MESSAGE_QUEUE_SIZE: 100,
} as const;

// Security
export const SECURITY_CONFIG = {
  JWT_EXPIRES_IN: '7d',
  REFRESH_TOKEN_EXPIRES_IN: '30d',
  PASSWORD_MIN_LENGTH: 6,
  PASSWORD_MAX_LENGTH: 128,
  MAX_LOGIN_ATTEMPTS: 5,
  LOCKOUT_DURATION: 15 * 60 * 1000, // 15 minutes
  BCRYPT_ROUNDS: 12,
} as const;

// Rate Limiting
export const RATE_LIMIT = {
  WINDOW_MS: 15 * 60 * 1000, // 15 minutes
  MAX_REQUESTS: 100,
  SKIP_SUCCESSFUL_REQUESTS: false,
  SKIP_FAILED_REQUESTS: false,
} as const;

// Device Management
export const DEVICE_CONFIG = {
  HEARTBEAT_TIMEOUT: 5 * 60 * 1000, // 5 minutes
  OFFLINE_TIMEOUT: 10 * 60 * 1000, // 10 minutes
  MAX_DEVICE_NAME_LENGTH: 100,
  MAX_METADATA_SIZE: 1024 * 10, // 10KB
} as const;

// Detection Configuration
export const DETECTION_CONFIG = {
  MIN_CONFIDENCE: 0.1,
  MAX_CONFIDENCE: 1.0,
  BATCH_SIZE: 100,
  RETENTION_DAYS: 30,
  MAX_CLASSES_PER_DETECTION: 10,
} as const;

// API Response Messages
export const API_MESSAGES = {
  SUCCESS: {
    CREATED: 'Resource created successfully',
    UPDATED: 'Resource updated successfully',
    DELETED: 'Resource deleted successfully',
    RETRIEVED: 'Resource retrieved successfully',
  },
  ERROR: {
    NOT_FOUND: 'Resource not found',
    UNAUTHORIZED: 'Unauthorized access',
    FORBIDDEN: 'Access forbidden',
    VALIDATION_FAILED: 'Validation failed',
    INTERNAL_ERROR: 'Internal server error',
    BAD_REQUEST: 'Bad request',
  },
  AUTH: {
    LOGIN_SUCCESS: 'Login successful',
    LOGIN_FAILED: 'Invalid credentials',
    LOGOUT_SUCCESS: 'Logout successful',
    TOKEN_EXPIRED: 'Token expired',
    TOKEN_INVALID: 'Invalid token',
    PASSWORD_CHANGED: 'Password changed successfully',
    ACCOUNT_LOCKED: 'Account locked due to too many failed attempts',
  },
  DEVICE: {
    REGISTERED: 'Device registered successfully',
    HEARTBEAT_RECEIVED: 'Heartbeat received',
    STATUS_UPDATED: 'Device status updated',
    OFFLINE: 'Device is offline',
    ONLINE: 'Device is online',
  },
  FILE: {
    UPLOAD_STARTED: 'File upload started',
    UPLOAD_COMPLETED: 'File upload completed',
    UPLOAD_FAILED: 'File upload failed',
    FILE_TOO_LARGE: 'File size exceeds maximum allowed size',
    UNSUPPORTED_TYPE: 'File type not supported',
  },
} as const;

// HTTP Status Codes
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  UNPROCESSABLE_ENTITY: 422,
  TOO_MANY_REQUESTS: 429,
  INTERNAL_SERVER_ERROR: 500,
  SERVICE_UNAVAILABLE: 503,
} as const;