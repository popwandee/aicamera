import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { Camera } from './camera.entity';
import { Visualization } from './visualization.entity';

export type EventCategory =
  | 'user_interaction'
  | 'system_event'
  | 'performance'
  | 'error'
  | 'security';

@Entity('analytics_events')
export class AnalyticsEvent {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'event_type', type: 'varchar', length: 100 })
  eventType: string;

  @Column({
    name: 'event_category',
    type: 'varchar',
    length: 50,
  })
  eventCategory: EventCategory;

  @Column({ name: 'user_id', type: 'varchar', length: 100, nullable: true })
  userId: string | null;

  @Column({ name: 'session_id', type: 'varchar', length: 100, nullable: true })
  sessionId: string | null;

  @Column({ name: 'camera_id', type: 'uuid', nullable: true })
  cameraId: string | null;

  @ManyToOne(() => Camera, { onDelete: 'SET NULL' })
  @JoinColumn({ name: 'camera_id' })
  camera: Camera | null;

  @Column({ name: 'visualization_id', type: 'uuid', nullable: true })
  visualizationId: string | null;

  @ManyToOne(() => Visualization, { onDelete: 'SET NULL' })
  @JoinColumn({ name: 'visualization_id' })
  visualization: Visualization | null;

  @Column({ name: 'event_data', type: 'jsonb', default: {} })
  eventData: Record<string, unknown>;

  @Column({ name: 'ip_address', type: 'inet', nullable: true })
  ipAddress: string | null;

  @Column({ name: 'user_agent', type: 'text', nullable: true })
  userAgent: string | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}
