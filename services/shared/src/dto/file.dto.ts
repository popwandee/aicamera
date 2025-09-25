import { IsString, IsNumber, IsOptional, IsEnum, IsObject, IsDateString, Min, Max } from 'class-validator';
import { FileStatus } from '../interfaces/file.interface';

export class CreateFileDto {
  @IsString()
  deviceId: string;

  @IsString()
  filename: string;

  @IsOptional()
  @IsString()
  originalName?: string;

  @IsString()
  mimeType: string;

  @IsNumber()
  @Min(1)
  size: number;

  @IsOptional()
  @IsString()
  checksum?: string;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}

export class UpdateFileDto {
  @IsOptional()
  @IsEnum(FileStatus)
  status?: FileStatus;

  @IsOptional()
  @IsNumber()
  @Min(1)
  width?: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  height?: number;

  @IsOptional()
  @IsString()
  format?: string;

  @IsOptional()
  @IsString()
  thumbnailPath?: string;

  @IsOptional()
  @IsString()
  previewPath?: string;

  @IsOptional()
  @IsString()
  transferMethod?: string;

  @IsOptional()
  @IsString()
  checksum?: string;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}

export class FileUploadRequestDto {
  @IsString()
  deviceId: string;

  @IsString()
  filename: string;

  @IsString()
  mimeType: string;

  @IsNumber()
  @Min(1)
  size: number;

  @IsOptional()
  @IsString()
  checksum?: string;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}

export class FileTransferStatusDto {
  @IsString()
  fileId: string;

  @IsEnum(FileStatus)
  status: FileStatus;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(100)
  progress?: number;

  @IsOptional()
  @IsString()
  error?: string;

  @IsOptional()
  @IsNumber()
  @Min(0)
  estimatedTimeRemaining?: number;
}

export class FileFilterDto {
  @IsOptional()
  @IsString()
  deviceId?: string;

  @IsOptional()
  @IsEnum(FileStatus)
  status?: FileStatus;

  @IsOptional()
  @IsString()
  mimeType?: string;

  @IsOptional()
  @IsDateString()
  startDate?: string;

  @IsOptional()
  @IsDateString()
  endDate?: string;

  @IsOptional()
  @IsNumber()
  @Min(1)
  minSize?: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  maxSize?: number;

  @IsOptional()
  @IsString()
  hasDetections?: 'true' | 'false';

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
  sortBy?: string = 'createdAt';

  @IsOptional()
  @IsEnum(['asc', 'desc'])
  sortOrder?: 'asc' | 'desc' = 'desc';
}