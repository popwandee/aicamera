import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Camera } from './camera.entity';

@Entity('camera_health')
export class CameraHealth {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'camera_id', type: 'uuid' })
  cameraId: string;

  @ManyToOne(() => Camera, (c) => c.healthRecords, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'camera_id' })
  camera: Camera;

  @Column({ type: 'timestamptz', default: () => 'CURRENT_TIMESTAMP' })
  timestamp: Date;

  @Column({ type: 'varchar', length: 50 })
  status: string;

  @Column({ name: 'cpu_usage', type: 'decimal', precision: 5, scale: 2, nullable: true })
  cpuUsage: string | null;

  @Column({ name: 'memory_usage', type: 'decimal', precision: 5, scale: 2, nullable: true })
  memoryUsage: string | null;

  @Column({ name: 'disk_usage', type: 'decimal', precision: 5, scale: 2, nullable: true })
  diskUsage: string | null;

  @Column({ type: 'decimal', precision: 5, scale: 2, nullable: true })
  temperature: string | null;

  @Column({ name: 'uptime_seconds', type: 'bigint', nullable: true })
  uptimeSeconds: string | null;

  @Column({ name: 'last_detection_at', type: 'timestamptz', nullable: true })
  lastDetectionAt: Date | null;

  @Column({ type: 'jsonb', default: {} })
  metadata: Record<string, unknown>;
}
