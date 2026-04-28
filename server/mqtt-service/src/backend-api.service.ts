import { Injectable } from '@nestjs/common';
import axios, { AxiosInstance } from 'axios';

const DEFAULT_BACKEND_URL = 'http://localhost:3000/server/api';

export interface CameraRegisterPayload {
  camera_id: string;
  checkpoint_id?: string;
  timestamp?: string;
}

export interface MqttHealthPayload {
  camera_id?: string;
  device_id?: string;
  checkpoint_id?: string;
  status?: string;
  timestamp?: string;
  // Standard field names (original)
  cpu_percent?: number;
  memory_percent?: number;
  disk_free_gb?: number;
  temperature_c?: number;
  uptime_seconds?: number;
  // Actual field names sent by aicamera2 edge device
  cpu_usage?: number;
  cpu_temp?: number;
  memory_usage?: number;
  disk_usage?: number;
  uptime?: number;
  battery_percent?: number;
  network_connected?: boolean;
  location_lat?: number;
  location_lng?: number;
  [key: string]: unknown;
}

export interface CameraResponse {
  id: string;
  cameraId: string;
  name: string;
}

@Injectable()
export class BackendApiService {
  private readonly client: AxiosInstance;

  constructor() {
    const baseURL = process.env.BACKEND_API_URL || DEFAULT_BACKEND_URL;
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      maxRedirects: 5,
    });
  }

  async registerCamera(payload: CameraRegisterPayload): Promise<CameraResponse> {
    const { data } = await this.client.post<CameraResponse>('/cameras/register', {
      camera_id: payload.camera_id,
      checkpoint_id: payload.checkpoint_id || payload.camera_id,
      timestamp: payload.timestamp,
    });
    return data;
  }

  async createCameraHealth(
    cameraIdUuid: string,
    payload: MqttHealthPayload,
  ): Promise<{ id: string }> {
    const timestamp = payload.timestamp || new Date().toISOString();

    // Parse details string — edge sends component metrics (cpu_percent, ram_percent, cpu_temp)
    // inside a JSON-encoded 'details' field rather than as top-level payload fields.
    let parsedDetails: Record<string, unknown> = {};
    if (typeof payload.details === 'string') {
      try { parsedDetails = JSON.parse(payload.details) as Record<string, unknown>; } catch { /* ignore */ }
    } else if (payload.details && typeof payload.details === 'object') {
      parsedDetails = payload.details as Record<string, unknown>;
    }

    // Resolve field values — top-level fields first, then fall back to parsed details
    const cpuUsageVal = payload.cpu_percent ?? payload.cpu_usage ??
      (typeof parsedDetails.cpu_percent === 'number' ? parsedDetails.cpu_percent : undefined);
    const memUsageVal = payload.memory_percent ?? payload.memory_usage ??
      (typeof parsedDetails.ram_percent === 'number' ? parsedDetails.ram_percent : undefined);
    const tempVal = payload.temperature_c ?? payload.cpu_temp ??
      (typeof parsedDetails.cpu_temp === 'number' ? parsedDetails.cpu_temp : undefined);
    const uptimeVal = payload.uptime_seconds ?? payload.uptime;
    const diskUsageVal = payload.disk_usage ??
      (typeof parsedDetails.used_percent === 'number' ? parsedDetails.used_percent : undefined);

    const status =
      payload.status ||
      (cpuUsageVal != null && cpuUsageVal > 90 ? 'degraded' : 'healthy');

    // Strip mapped and administrative fields from metadata
    const metadata: Record<string, unknown> = { ...payload };
    for (const k of [
      'camera_id', 'device_id', 'checkpoint_id', 'timestamp', 'status',
      'cpu_percent', 'cpu_usage', 'memory_percent', 'memory_usage',
      'temperature_c', 'cpu_temp', 'uptime_seconds', 'uptime',
      'disk_usage',
    ]) {
      delete metadata[k];
    }

    const body: Record<string, unknown> = {
      cameraId: cameraIdUuid,
      timestamp,
      status: String(status).slice(0, 50),
      metadata,
    };
    if (cpuUsageVal != null) body['cpuUsage'] = Number(cpuUsageVal);
    if (memUsageVal != null) body['memoryUsage'] = Number(memUsageVal);
    if (tempVal != null) body['temperature'] = Number(tempVal);
    if (uptimeVal != null) body['uptimeSeconds'] = Number(uptimeVal);
    if (diskUsageVal != null) body['diskUsage'] = Number(diskUsageVal);
    if (payload.disk_free_gb != null) metadata['disk_free_gb'] = payload.disk_free_gb;

    const { data } = await this.client.post<{ id: string }>('/camera-health', body);
    return data;
  }
}
