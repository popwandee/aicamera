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

@Entity('analytics')
export class Analytics {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'camera_id', type: 'uuid' })
  cameraId: string;

  @ManyToOne(() => Camera, (c) => c.analytics, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'camera_id' })
  camera: Camera;

  @Column({ type: 'date' })
  date: string;

  @Column({ name: 'total_detections', type: 'int', default: 0 })
  totalDetections: number;

  @Column({ name: 'unique_plates', type: 'int', default: 0 })
  uniquePlates: number;

  @Column({ name: 'average_confidence', type: 'decimal', precision: 3, scale: 2, default: 0 })
  averageConfidence: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
