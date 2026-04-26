import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Camera } from './camera.entity';

export type EventLevel = 'debug' | 'info' | 'warning' | 'error' | 'critical';

@Entity('system_events')
export class SystemEvent {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'camera_id', type: 'uuid', nullable: true })
  cameraId: string | null;

  @ManyToOne(() => Camera, (c) => c.systemEvents, { onDelete: 'SET NULL' })
  @JoinColumn({ name: 'camera_id' })
  camera: Camera | null;

  @Column({ name: 'event_type', type: 'varchar', length: 100 })
  eventType: string;

  @Column({ name: 'event_level', type: 'varchar', length: 20 })
  eventLevel: EventLevel;

  @Column({ type: 'text' })
  message: string;

  @Column({ type: 'jsonb', default: {} })
  metadata: Record<string, unknown>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
