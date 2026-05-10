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
  camera_name?: string;
  ip_address?: string;
  camera_location?: string;
  location_lat?: string;
  location_lon?: string;
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
  uptime_seconds?: number;
  [key: string]: unknown;
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

  async createSystemEvent(payload: {
    cameraId?: string | null;
    eventType: string;
    eventLevel: 'debug' | 'info' | 'warning' | 'error' | 'critical';
    message: string;
    metadata?: Record<string, unknown>;
  }): Promise<void> {
    await this.client.post('/system-events', payload);
  }

  async createCameraHealth(
    cameraIdUuid: string,
    payload: HealthStatusPayload,
  ): Promise<{ id: string }> {
    const timestamp = payload.timestamp || payload.created_at || new Date().toISOString();

    // Parse details string — edge encodes component metrics inside a JSON 'details' field
    let parsedDetails: Record<string, unknown> = {};
    if (typeof payload.details === 'string') {
      try { parsedDetails = JSON.parse(payload.details) as Record<string, unknown>; } catch { /* ignore */ }
    } else if (payload.details && typeof payload.details === 'object') {
      parsedDetails = payload.details as Record<string, unknown>;
    }

    const cpuUsageVal  = typeof parsedDetails.cpu_percent === 'number'       ? parsedDetails.cpu_percent       : undefined;
    const memUsageVal  = typeof parsedDetails.ram_percent === 'number'       ? parsedDetails.ram_percent       : undefined;
    const tempVal      = typeof parsedDetails.cpu_temp === 'number'          ? parsedDetails.cpu_temp          : undefined;
    const diskUsageVal = typeof parsedDetails.disk_used_percent === 'number' ? parsedDetails.disk_used_percent : undefined;
    const uptimeVal    = typeof (payload as Record<string, unknown>).uptime_seconds === 'number'
      ? (payload as Record<string, unknown>).uptime_seconds as number : undefined;

    const metadata: Record<string, unknown> = {
      component: payload.component,
      message: payload.message,
      details: Object.keys(parsedDetails).length ? parsedDetails : (payload.details ?? {}),
    };

    const body: Record<string, unknown> = {
      cameraId: cameraIdUuid,
      timestamp,
      status: payload.status,
      metadata,
    };
    if (cpuUsageVal  != null) body['cpuUsage']      = cpuUsageVal;
    if (memUsageVal  != null) body['memoryUsage']   = memUsageVal;
    if (tempVal      != null) body['temperature']   = tempVal;
    if (diskUsageVal != null) body['diskUsage']     = diskUsageVal;
    if (uptimeVal    != null) body['uptimeSeconds'] = uptimeVal;

    const { data } = await this.client.post<{ id: string }>('/camera-health', body);
    return data;
  }
}
