import { IsString, IsEnum, IsNumber, IsOptional, IsArray, IsObject, IsUUID, IsDateString, Min, Max, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';
import { DetectionType } from '../interfaces/detection.interface';

export class BoundingBoxDto {
  @IsNumber()
  @Min(0)
  @Max(1)
  x: number;

  @IsNumber()
  @Min(0)
  @Max(1)
  y: number;

  @IsNumber()
  @Min(0)
  @Max(1)
  width: number;

  @IsNumber()
  @Min(0)
  @Max(1)
  height: number;
}

export class ClassificationResultDto {
  @IsString()
  label: string;

  @IsNumber()
  @Min(0)
  @Max(1)
  confidence: number;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}

export class CreateDetectionDto {
  @IsString()
  deviceId: string;

  @IsEnum(DetectionType)
  type: DetectionType;

  @IsNumber()
  @Min(0)
  @Max(1)
  confidence: number;

  @IsOptional()
  @ValidateNested()
  @Type(() => BoundingBoxDto)
  boundingBox?: BoundingBoxDto;

  @IsOptional()
  @IsString()
  label?: string;

  @IsOptional()
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => ClassificationResultDto)
  classes?: ClassificationResultDto[];

  @IsOptional()
  @IsObject()
  rawData?: Record<string, any>;

  @IsOptional()
  @IsUUID()
  imageId?: string;

  @IsOptional()
  @IsString()
  trackingId?: string;

  @IsOptional()
  @IsDateString()
  timestamp?: string;
}

export class BulkCreateDetectionDto {
  @IsString()
  deviceId: string;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => CreateDetectionDto)
  detections: CreateDetectionDto[];
}

export class DetectionFilterDto {
  @IsOptional()
  @IsString()
  deviceId?: string;

  @IsOptional()
  @IsEnum(DetectionType)
  type?: DetectionType;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(1)
  minConfidence?: number;

  @IsOptional()
  @IsDateString()
  startDate?: string;

  @IsOptional()
  @IsDateString()
  endDate?: string;

  @IsOptional()
  @IsString()
  label?: string;

  @IsOptional()
  @IsString()
  trackingId?: string;

  @IsOptional()
  @IsString()
  hasImage?: 'true' | 'false';

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

export class DetectionStatsDto {
  @IsOptional()
  @IsString()
  deviceId?: string;

  @IsOptional()
  @IsDateString()
  startDate?: string;

  @IsOptional()
  @IsDateString()
  endDate?: string;

  @IsOptional()
  @IsString()
  groupBy?: 'hour' | 'day' | 'week' | 'month' = 'day';
}