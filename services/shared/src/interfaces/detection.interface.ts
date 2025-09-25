export interface IDetection {
  id: string;
  deviceId: string;
  type: DetectionType;
  confidence: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  label?: string;
  classes?: ClassificationResult[];
  rawData?: Record<string, any>;
  imageId?: string;
  trackingId?: string;
  createdAt: Date;
}

export interface IDetectionRequest {
  deviceId: string;
  type: DetectionType;
  confidence: number;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  label?: string;
  classes?: ClassificationResult[];
  rawData?: Record<string, any>;
  imageId?: string;
  trackingId?: string;
  timestamp?: Date;
}

export interface ClassificationResult {
  label: string;
  confidence: number;
  metadata?: Record<string, any>;
}

export interface IDetectionFilter {
  deviceId?: string;
  type?: DetectionType;
  minConfidence?: number;
  startDate?: Date;
  endDate?: Date;
  hasImage?: boolean;
  limit?: number;
  offset?: number;
}

export interface IDetectionStats {
  totalDetections: number;
  detectionsByType: Record<DetectionType, number>;
  detectionsByDevice: Record<string, number>;
  averageConfidence: number;
  detectionsToday: number;
  detectionsThisWeek: number;
  detectionsThisMonth: number;
}

export enum DetectionType {
  OBJECT = 'OBJECT',
  FACE = 'FACE',
  PERSON = 'PERSON',
  VEHICLE = 'VEHICLE',
  ANIMAL = 'ANIMAL',
  OTHER = 'OTHER',
}