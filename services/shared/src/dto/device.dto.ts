import { IsString, IsEnum, IsOptional, IsNumber, IsObject, IsUUID, IsDateString, IsBoolean, Min, Max } from 'class-validator';
import { EdgeDeviceType, DeviceStatus, LogLevel } from '../interfaces/device.interface';

export class CreateDeviceDto {
  @IsString()
  deviceId: string;

  @IsString()
  name: string;

  @IsEnum(EdgeDeviceType)
  type: EdgeDeviceType;

  @IsOptional()
  @IsString()
  location?: string;

  @IsOptional()
  @IsNumber()
  @Min(-90)
  @Max(90)
  latitude?: number;

  @IsOptional()
  @IsNumber()
  @Min(-180)
  @Max(180)
  longitude?: number;

  @IsOptional()
  @IsObject()
  capabilities?: Record<string, any>;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}

export class UpdateDeviceDto {
  @IsOptional()
  @IsString()
  name?: string;

  @IsOptional()
  @IsEnum(EdgeDeviceType)
  type?: EdgeDeviceType;

  @IsOptional()
  @IsEnum(DeviceStatus)
  status?: DeviceStatus;

  @IsOptional()
  @IsString()
  ipAddress?: string;

  @IsOptional()
  @IsString()
  macAddress?: string;

  @IsOptional()
  @IsString()
  version?: string;

  @IsOptional()
  @IsString()
  location?: string;

  @IsOptional()
  @IsNumber()
  @Min(-90)
  @Max(90)
  latitude?: number;

  @IsOptional()
  @IsNumber()
  @Min(-180)
  @Max(180)
  longitude?: number;

  @IsOptional()
  @IsObject()
  capabilities?: Record<string, any>;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}

export class DeviceHeartbeatDto {
  @IsString()
  deviceId: string;

  @IsEnum(DeviceStatus)
  status: DeviceStatus;

  @IsOptional()
  @IsDateString()
  timestamp?: string;

  @IsOptional()
  @IsObject()
  systemInfo?: {
    cpuUsage?: number;
    memoryUsage?: number;
    diskUsage?: number;
    temperature?: number;
    uptime?: number;
  };

  @IsOptional()
  @IsObject()
  networkInfo?: {
    ipAddress?: string;
    macAddress?: string;
    signalStrength?: number;
  };
}

export class CreateDeviceLogDto {
  @IsString()
  deviceId: string;

  @IsEnum(LogLevel)
  level: LogLevel;

  @IsString()
  message: string;

  @IsOptional()
  @IsObject()
  data?: Record<string, any>;
}

export class DeviceFilterDto {
  @IsOptional()
  @IsEnum(EdgeDeviceType)
  type?: EdgeDeviceType;

  @IsOptional()
  @IsEnum(DeviceStatus)
  status?: DeviceStatus;

  @IsOptional()
  @IsString()
  location?: string;

  @IsOptional()
  @IsString()
  search?: string;

  @IsOptional()
  @IsNumber()
  @Min(1)
  limit?: number = 10;

  @IsOptional()
  @IsNumber()
  @Min(0)
  offset?: number = 0;

  @IsOptional()
  @IsString()
  sortBy?: string = 'name';

  @IsOptional()
  @IsEnum(['asc', 'desc'])
  sortOrder?: 'asc' | 'desc' = 'asc';
}