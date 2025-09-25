export enum LogLevel {
  ERROR = 0,
  WARN = 1,
  INFO = 2,
  DEBUG = 3,
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  service?: string;
  deviceId?: string;
  userId?: string;
  requestId?: string;
  data?: Record<string, any>;
  error?: Error;
}

export class Logger {
  private serviceName: string;
  private logLevel: LogLevel;

  constructor(serviceName: string, logLevel: LogLevel = LogLevel.INFO) {
    this.serviceName = serviceName;
    this.logLevel = logLevel;
  }

  private createLogEntry(
    level: LogLevel,
    message: string,
    data?: Record<string, any>,
    error?: Error
  ): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level: LogLevel[level],
      message,
      service: this.serviceName,
      data,
      error,
    };
  }

  private shouldLog(level: LogLevel): boolean {
    return level <= this.logLevel;
  }

  private formatLogEntry(entry: LogEntry): string {
    let logString = `[${entry.timestamp}] [${entry.service}] ${entry.level}: ${entry.message}`;

    if (entry.deviceId) {
      logString += ` [Device: ${entry.deviceId}]`;
    }

    if (entry.userId) {
      logString += ` [User: ${entry.userId}]`;
    }

    if (entry.requestId) {
      logString += ` [Request: ${entry.requestId}]`;
    }

    if (entry.data && Object.keys(entry.data).length > 0) {
      logString += `\nData: ${JSON.stringify(entry.data, null, 2)}`;
    }

    if (entry.error) {
      logString += `\nError: ${entry.error.message}`;
      if (entry.error.stack) {
        logString += `\nStack: ${entry.error.stack}`;
      }
    }

    return logString;
  }

  private writeLog(entry: LogEntry): void {
    const formattedLog = this.formatLogEntry(entry);

    switch (entry.level) {
      case 'ERROR':
        console.error(formattedLog);
        break;
      case 'WARN':
        console.warn(formattedLog);
        break;
      case 'INFO':
        console.info(formattedLog);
        break;
      case 'DEBUG':
        console.debug(formattedLog);
        break;
      default:
        console.log(formattedLog);
    }
  }

  error(message: string, error?: Error, data?: Record<string, any>): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      const entry = this.createLogEntry(LogLevel.ERROR, message, data, error);
      this.writeLog(entry);
    }
  }

  warn(message: string, data?: Record<string, any>): void {
    if (this.shouldLog(LogLevel.WARN)) {
      const entry = this.createLogEntry(LogLevel.WARN, message, data);
      this.writeLog(entry);
    }
  }

  info(message: string, data?: Record<string, any>): void {
    if (this.shouldLog(LogLevel.INFO)) {
      const entry = this.createLogEntry(LogLevel.INFO, message, data);
      this.writeLog(entry);
    }
  }

  debug(message: string, data?: Record<string, any>): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      const entry = this.createLogEntry(LogLevel.DEBUG, message, data);
      this.writeLog(entry);
    }
  }

  // Context-specific logging methods
  deviceLog(
    deviceId: string,
    level: LogLevel,
    message: string,
    data?: Record<string, any>
  ): void {
    if (this.shouldLog(level)) {
      const entry = this.createLogEntry(level, message, data);
      entry.deviceId = deviceId;
      this.writeLog(entry);
    }
  }

  userLog(
    userId: string,
    level: LogLevel,
    message: string,
    data?: Record<string, any>
  ): void {
    if (this.shouldLog(level)) {
      const entry = this.createLogEntry(level, message, data);
      entry.userId = userId;
      this.writeLog(entry);
    }
  }

  requestLog(
    requestId: string,
    level: LogLevel,
    message: string,
    data?: Record<string, any>
  ): void {
    if (this.shouldLog(level)) {
      const entry = this.createLogEntry(level, message, data);
      entry.requestId = requestId;
      this.writeLog(entry);
    }
  }

  // Convenience methods for common scenarios
  httpRequest(method: string, url: string, statusCode: number, responseTime: number): void {
    this.info(`${method} ${url}`, {
      statusCode,
      responseTime: `${responseTime}ms`,
    });
  }

  databaseQuery(query: string, duration: number): void {
    this.debug('Database query executed', {
      query,
      duration: `${duration}ms`,
    });
  }

  mqttMessage(topic: string, payload: any): void {
    this.debug('MQTT message', {
      topic,
      payload,
    });
  }

  websocketEvent(event: string, deviceId?: string): void {
    this.debug('WebSocket event', {
      event,
      deviceId,
    });
  }

  fileOperation(operation: string, filename: string, size?: number): void {
    this.info(`File ${operation}`, {
      filename,
      size: size ? `${size} bytes` : undefined,
    });
  }

  detection(deviceId: string, type: string, confidence: number): void {
    this.info('Detection received', {
      deviceId,
      type,
      confidence,
    });
  }

  deviceStatus(deviceId: string, status: string, previousStatus?: string): void {
    this.info('Device status changed', {
      deviceId,
      status,
      previousStatus,
    });
  }

  // Static factory method
  static create(serviceName: string, logLevel?: LogLevel): Logger {
    const envLogLevel = process.env.LOG_LEVEL?.toUpperCase();
    let resolvedLogLevel = logLevel || LogLevel.INFO;

    if (envLogLevel) {
      switch (envLogLevel) {
        case 'ERROR':
          resolvedLogLevel = LogLevel.ERROR;
          break;
        case 'WARN':
          resolvedLogLevel = LogLevel.WARN;
          break;
        case 'INFO':
          resolvedLogLevel = LogLevel.INFO;
          break;
        case 'DEBUG':
          resolvedLogLevel = LogLevel.DEBUG;
          break;
      }
    }

    return new Logger(serviceName, resolvedLogLevel);
  }
}