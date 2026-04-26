import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';
import { Detection } from './detection.entity';
import { Analytics } from './analytics.entity';
import { CameraHealth } from './camera-health.entity';
import { SystemEvent } from './system-event.entity';

export type CameraStatus = 'active' | 'inactive' | 'maintenance';
export type ImageQuality = 'low' | 'medium' | 'high';

@Entity('cameras')
export class Camera {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'camera_id', type: 'varchar', length: 50, unique: true })
  cameraId: string;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ name: 'location_lat', type: 'decimal', precision: 10, scale: 8, nullable: true })
  locationLat: string | null;

  @Column({ name: 'location_lng', type: 'decimal', precision: 11, scale: 8, nullable: true })
  locationLng: string | null;

  @Column({ name: 'location_address', type: 'text', nullable: true })
  locationAddress: string | null;

  @Column({ type: 'enum', enum: ['active', 'inactive', 'maintenance'], default: 'active' })
  status: CameraStatus;

  @Column({ name: 'detection_enabled', type: 'boolean', default: true })
  detectionEnabled: boolean;

  @Column({ name: 'image_quality', type: 'enum', enum: ['low', 'medium', 'high'], default: 'medium' })
  imageQuality: ImageQuality;

  @Column({ name: 'upload_interval', type: 'int', default: 60 })
  uploadInterval: number;

  @Column({ type: 'jsonb', default: {} })
  configuration: Record<string, unknown>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @OneToMany(() => Detection, (d) => d.camera)
  detections: Detection[];

  @OneToMany(() => Analytics, (a) => a.camera)
  analytics: Analytics[];

  @OneToMany(() => CameraHealth, (h) => h.camera)
  healthRecords: CameraHealth[];

  @OneToMany(() => SystemEvent, (e) => e.camera)
  systemEvents: SystemEvent[];
}
