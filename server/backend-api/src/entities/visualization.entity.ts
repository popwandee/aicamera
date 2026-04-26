import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export type VisualizationType = 'chart' | 'graph' | 'table' | 'metric' | 'map';

@Entity('visualizations')
export class Visualization {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ type: 'text', nullable: true })
  description: string | null;

  @Column({ type: 'varchar', length: 50 })
  type: VisualizationType;

  @Column({ type: 'jsonb', default: {} })
  configuration: Record<string, unknown>;

  @Column({ name: 'data_source', type: 'varchar', length: 100 })
  dataSource: string;

  @Column({ name: 'refresh_interval', type: 'int', default: 300 })
  refreshInterval: number;

  @Column({ name: 'is_active', type: 'boolean', default: true })
  isActive: boolean;

  @Column({ name: 'created_by', type: 'varchar', length: 100, nullable: true })
  createdBy: string | null;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}
