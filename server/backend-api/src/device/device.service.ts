import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, DataSource } from 'typeorm';
import {
  Camera,
  Detection,
  Analytics,
  CameraHealth,
  SystemEvent,
  Visualization,
  AnalyticsEvent,
} from '../entities';

export interface CameraSummaryRow {
  id: string;
  camera_id: string;
  name: string;
  status: string;
  location_lat: string | null;
  location_lng: string | null;
  location_address: string | null;
  total_detections: string;
  unique_plates: string;
  average_confidence: string | null;
  last_detection: Date | null;
  created_at: Date;
  updated_at: Date;
}

@Injectable()
export class DeviceService {
  constructor(
    @InjectRepository(Camera)
    private readonly cameraRepo: Repository<Camera>,
    @InjectRepository(Detection)
    private readonly detectionRepo: Repository<Detection>,
    @InjectRepository(Analytics)
    private readonly analyticsRepo: Repository<Analytics>,
    @InjectRepository(CameraHealth)
    private readonly cameraHealthRepo: Repository<CameraHealth>,
    @InjectRepository(SystemEvent)
    private readonly systemEventRepo: Repository<SystemEvent>,
    @InjectRepository(Visualization)
    private readonly visualizationRepo: Repository<Visualization>,
    @InjectRepository(AnalyticsEvent)
    private readonly analyticsEventRepo: Repository<AnalyticsEvent>,
    private readonly dataSource: DataSource,
  ) {}

  async findAllCameras(): Promise<Camera[]> {
    return this.cameraRepo.find({ order: { createdAt: 'DESC' } });
  }

  async findCameraById(id: string): Promise<Camera | null> {
    return this.cameraRepo.findOne({ where: { id } });
  }

  async findCameraByCameraId(cameraId: string): Promise<Camera | null> {
    return this.cameraRepo.findOne({ where: { cameraId } });
  }

  async createCamera(data: Partial<Camera>): Promise<Camera> {
    const camera = this.cameraRepo.create(data);
    return this.cameraRepo.save(camera);
  }

  async updateCamera(id: string, data: Partial<Camera>): Promise<Camera> {
    await this.cameraRepo.update(id, data as Record<string, unknown>);
    const updated = await this.cameraRepo.findOne({ where: { id } });
    if (!updated) throw new Error('Camera not found');
    return updated;
  }

  async deleteCamera(id: string): Promise<void> {
    await this.cameraRepo.delete(id);
  }

  async findAllDetections(
    cameraId?: string,
    limit = 100,
    offset = 0,
    archived?: boolean,
    search?: string,
    sortBy = 'timestamp',
    sortOrder: 'ASC' | 'DESC' = 'DESC',
  ): Promise<Detection[]> {
    const qb = this.detectionRepo
      .createQueryBuilder('d')
      .leftJoinAndSelect('d.camera', 'c')
      .take(limit)
      .skip(offset);
    if (cameraId) qb.andWhere('d.camera_id = :cameraId', { cameraId });
    if (typeof archived === 'boolean') {
      qb.andWhere('d.archived = :archived', { archived });
    }
    if (search && search.trim()) {
      qb.andWhere('(d.license_plate ILIKE :search OR d.id::text ILIKE :search)', {
        search: `%${search.trim()}%`,
      });
    }
    const orderCol = ['timestamp', 'licensePlate', 'confidence', 'createdAt'].includes(sortBy)
      ? `d.${sortBy}`
      : 'd.timestamp';
    const order: 'ASC' | 'DESC' = sortOrder === 'ASC' ? 'ASC' : 'DESC';
    qb.orderBy(orderCol, order);
    return qb.getMany();
  }

  async findDetectionsByCameraId(cameraId: string, limit = 100): Promise<Detection[]> {
    return this.detectionRepo.find({
      where: { cameraId },
      relations: ['camera'],
      order: { timestamp: 'DESC' },
      take: limit,
    });
  }

  async createDetection(data: Partial<Detection>): Promise<Detection> {
    const detection = this.detectionRepo.create(data);
    return this.detectionRepo.save(detection);
  }

  async getCameraSummary(): Promise<CameraSummaryRow[]> {
    const rows = await this.dataSource.query('SELECT * FROM camera_summary');
    return rows as CameraSummaryRow[];
  }

  async runUpdateDailyAnalytics(): Promise<void> {
    await this.dataSource.query('SELECT update_daily_analytics()');
  }

  async findAllCameraHealth(
    cameraId?: string,
    limit = 200,
    from?: string,
    to?: string,
  ): Promise<CameraHealth[]> {
    const qb = this.cameraHealthRepo
      .createQueryBuilder('h')
      .leftJoinAndSelect('h.camera', 'c')
      .orderBy('h.timestamp', 'DESC')
      .take(limit);
    if (cameraId) qb.andWhere('h.camera_id = :cameraId', { cameraId });
    if (from) qb.andWhere('h.timestamp >= :from', { from });
    if (to) qb.andWhere('h.timestamp <= :to', { to });
    return qb.getMany();
  }

  async createCameraHealth(data: Partial<CameraHealth>): Promise<CameraHealth> {
    const health = this.cameraHealthRepo.create(data);
    return this.cameraHealthRepo.save(health);
  }

  /** Find camera by external camera_id (Edge), or create one. Used by ws-service on camera_register. */
  async registerCameraOrGet(payload: {
    camera_id: string;
    checkpoint_id: string;
    timestamp?: string;
  }): Promise<Camera> {
    const existing = await this.findCameraByCameraId(payload.camera_id);
    if (existing) return existing;
    return this.createCamera({
      cameraId: payload.camera_id,
      name: payload.checkpoint_id || payload.camera_id,
    });
  }

  async findDetectionById(id: string): Promise<Detection | null> {
    return this.detectionRepo.findOne({ where: { id } });
  }

  async updateDetection(id: string, data: Partial<Detection>): Promise<Detection> {
    if (data.archived === true) {
      (data as Record<string, unknown>).archivedAt = new Date();
    }
    await this.detectionRepo.update(id, data as Record<string, unknown>);
    const updated = await this.detectionRepo.findOne({ where: { id } });
    if (!updated) throw new Error('Detection not found');
    return updated;
  }

  async findAllAnalytics(limit = 500): Promise<Analytics[]> {
    return this.analyticsRepo.find({
      relations: ['camera'],
      order: { date: 'DESC' },
      take: limit,
    });
  }

  async findAllSystemEvents(limit = 500): Promise<SystemEvent[]> {
    return this.systemEventRepo.find({
      relations: ['camera'],
      order: { createdAt: 'DESC' },
      take: limit,
    });
  }

  async findAllVisualizations(limit = 500): Promise<Visualization[]> {
    return this.visualizationRepo.find({
      order: { createdAt: 'DESC' },
      take: limit,
    });
  }

  async findAllAnalyticsEvents(limit = 500): Promise<AnalyticsEvent[]> {
    return this.analyticsEventRepo.find({
      relations: ['camera', 'visualization'],
      order: { createdAt: 'DESC' },
      take: limit,
    });
  }

  /** For Edge Control dashboard: cameras with their latest camera_health (status, timestamp). */
  async findCamerasWithLatestHealth(): Promise<
    Array<{ camera: Camera; latestHealth: { status: string; timestamp: Date } | null }>
  > {
    const cameras = await this.cameraRepo.find({ order: { createdAt: 'DESC' } });
    const result: Array<{ camera: Camera; latestHealth: { status: string; timestamp: Date } | null }> = [];
    for (const camera of cameras) {
      const latest = await this.cameraHealthRepo.findOne({
        where: { cameraId: camera.id },
        order: { timestamp: 'DESC' },
        select: ['status', 'timestamp'],
      });
      result.push({
        camera,
        latestHealth: latest ? { status: latest.status, timestamp: latest.timestamp } : null,
      });
    }
    return result;
  }

  /** Delete camera_health rows older than the given number of days. */
  async deleteCameraHealthOlderThan(days: number): Promise<number> {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const result = await this.cameraHealthRepo
      .createQueryBuilder()
      .delete()
      .where('timestamp < :cutoff', { cutoff: cutoff.toISOString() })
      .execute();
    return result.affected ?? 0;
  }

  /** Update image_path for all detections of a camera in the given timestamp window (±1s). */
  async updateDetectionsImagePath(
    cameraId: string,
    timestampIso: string,
    imagePath: string,
  ): Promise<{ affected: number }> {
    const t = new Date(timestampIso);
    const start = new Date(t.getTime() - 1000);
    const end = new Date(t.getTime() + 1000);
    const result = await this.detectionRepo
      .createQueryBuilder()
      .update(Detection)
      .set({ imagePath })
      .where('camera_id = :cameraId', { cameraId })
      .andWhere('timestamp >= :start', { start: start.toISOString() })
      .andWhere('timestamp <= :end', { end: end.toISOString() })
      .execute();
    return { affected: result.affected ?? 0 };
  }
}
