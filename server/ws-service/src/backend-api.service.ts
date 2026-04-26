import { Injectable } from '@nestjs/common';
import axios, { AxiosInstance } from 'axios';

const DEFAULT_BACKEND_URL = 'http://localhost:3000/server/api';

function normalizeBackendApiBaseUrl(input: string): string {
  const trimmed = String(input || '').trim().replace(/\/+$/, '');
  if (!trimmed) return DEFAULT_BACKEND_URL;
  // ws-service must call backend-api with global prefix `/server/api`
  if (/\/server\/api$/i.test(trimmed)) return trimmed;
  return `${trimmed}/server/api`;
}

export interface CameraRegisterPayload {
  camera_id: string;
  checkpoint_id: string;
  timestamp?: string;
}

export interface DetectionResultContent {
  type: string;
  aicamera_id: string;
  checkpoint_id: string;
  timestamp: string;
  vehicles_count: number;
  plates_count: number;
  ocr_results: Array<{ text: string; confidence: number }>;
  vehicle_detections?: Array<{ bbox: number[]; confidence: number }>;
  plate_detections?: Array<{ bbox: number[]; confidence: number }>;
  processing_time_ms?: number;
  created_at?: string;
}

export interface HealthStatusPayload {
  type: string;
  aicamera_id: string;
  checkpoint_id: string;
  timestamp?: string;
  component: string;
  status: string;
  message: string;
  details?: string;
  created_at?: string;
}

export interface CameraResponse {
  id: string;
  cameraId: string;
  name: string;
}

export interface DetectionResponse {
  id: string;
}

@Injectable()
export class BackendApiService {
  private readonly client: AxiosInstance;

  constructor() {
    const baseURL = normalizeBackendApiBaseUrl(
      process.env.BACKEND_API_URL || DEFAULT_BACKEND_URL,
    );
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      maxRedirects: 5,
    });
  }

  async registerCamera(payload: CameraRegisterPayload): Promise<CameraResponse> {
    const { data } = await this.client.post<CameraResponse>(
      '/cameras/register',
      payload,
    );
    return data;
  }

  /** Parse value that may be JSON string (edge often sends ocr_results/vehicle_detections as string). */
  private parseJsonArray<T = unknown>(val: unknown): T[] {
    if (Array.isArray(val)) return val as T[];
    if (typeof val === 'string') {
      try {
        const parsed = JSON.parse(val);
        return Array.isArray(parsed) ? (parsed as T[]) : [];
      } catch {
        return [];
      }
    }
    return [];
  }

  async createDetections(
    cameraIdUuid: string,
    content: DetectionResultContent,
  ): Promise<DetectionResponse[]> {
    const timestamp = content.timestamp || content.created_at || new Date().toISOString();
    const results: DetectionResponse[] = [];
    const ocrResults = this.parseJsonArray<{ text?: string; confidence?: number }>(content.ocr_results as unknown);
    const vehicleDetections = this.parseJsonArray(content.vehicle_detections as unknown);
    const plateDetections = this.parseJsonArray(content.plate_detections as unknown);
    const metadata: Record<string, unknown> = {
      vehicles_count: content.vehicles_count,
      plates_count: content.plates_count,
      vehicle_detections: vehicleDetections,
      plate_detections: plateDetections,
      processing_time_ms: content.processing_time_ms,
    };
    for (const ocr of ocrResults) {
      const text = ocr && typeof ocr === 'object' && 'text' in ocr ? ocr.text : undefined;
      const licensePlate = (text != null ? String(text) : '-').slice(0, 20);
      const rawConf = ocr && typeof ocr === 'object' && 'confidence' in ocr ? ocr.confidence : 0;
      const confidence = Number(rawConf);
      const safeConfidence = Number.isFinite(confidence) ? Math.min(1, Math.max(0, confidence)) : 0;
      const { data } = await this.client.post<DetectionResponse>('/detections', {
        cameraId: cameraIdUuid,
        timestamp,
        licensePlate,
        confidence: safeConfidence,
        imagePath: null,
        metadata,
      });
      results.push(data);
    }
    if (results.length === 0 && (vehicleDetections.length > 0 || plateDetections.length > 0)) {
      const { data } = await this.client.post<DetectionResponse>('/detections', {
        cameraId: cameraIdUuid,
        timestamp,
        licensePlate: '-',
        confidence: 0,
        imagePath: null,
        metadata,
      });
      results.push(data);
    }
    return results;
  }

  async updateDetectionsImagePath(
    cameraIdUuid: string,
    timestampIso: string,
    imagePath: string,
  ): Promise<{ affected: number }> {
    const { data } = await this.client.patch<{ affected: number }>(
      '/detections/image-path',
      {
        cameraId: cameraIdUuid,
        timestamp: timestampIso,
        imagePath,
      },
    );
    return data;
  }

  async createCameraHealth(
    cameraIdUuid: string,
    payload: HealthStatusPayload,
  ): Promise<{ id: string }> {
    const timestamp = payload.timestamp || payload.created_at || new Date().toISOString();
    const metadata: Record<string, unknown> = {
      component: payload.component,
      message: payload.message,
      details: payload.details ?? {},
    };
    try {
      if (typeof metadata.details === 'string') {
        try {
          metadata.details = JSON.parse(metadata.details as string);
        } catch {
          // keep as string
        }
      }
    } catch {
      // ignore
    }
    const { data } = await this.client.post<{ id: string }>('/camera-health', {
      cameraId: cameraIdUuid,
      timestamp,
      status: payload.status,
      metadata,
    });
    return data;
  }
}
