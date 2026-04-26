import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Camera } from './camera.entity';

@Entity('detections')
export class Detection {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'camera_id', type: 'uuid' })
  cameraId: string;

  @ManyToOne(() => Camera, (c) => c.detections, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'camera_id' })
  camera: Camera;

  @Column({ type: 'timestamptz' })
  timestamp: Date;

  @Column({ name: 'license_plate', type: 'varchar', length: 20 })
  licensePlate: string;

  @Column({ type: 'decimal', precision: 3, scale: 2 })
  confidence: string;

  @Column({ name: 'image_url', type: 'text', nullable: true })
  imageUrl: string | null;

  @Column({ name: 'image_path', type: 'text', nullable: true })
  imagePath: string | null;

  @Column({ name: 'location_lat', type: 'decimal', precision: 10, scale: 8, nullable: true })
  locationLat: string | null;

  @Column({ name: 'location_lng', type: 'decimal', precision: 11, scale: 8, nullable: true })
  locationLng: string | null;

  @Column({ name: 'vehicle_make', type: 'varchar', length: 100, nullable: true })
  vehicleMake: string | null;

  @Column({ name: 'vehicle_model', type: 'varchar', length: 100, nullable: true })
  vehicleModel: string | null;

  @Column({ name: 'vehicle_color', type: 'varchar', length: 50, nullable: true })
  vehicleColor: string | null;

  @Column({ name: 'vehicle_type', type: 'varchar', length: 50, nullable: true })
  vehicleType: string | null;

  @Column({ type: 'enum', enum: ['pending', 'processed', 'failed'], default: 'pending' })
  status: string;

  @Column({ type: 'jsonb', default: {} })
  metadata: Record<string, unknown>;

  @Column({ default: false })
  archived: boolean;

  @Column({ name: 'archived_at', type: 'timestamptz', nullable: true })
  archivedAt: Date | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
