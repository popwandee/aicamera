export interface CameraLocation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  status: 'active' | 'inactive' | 'error' | 'maintenance';
  address: string;
  lastSeen: string;
  detectionCount: number;
  cameraType: 'fixed' | 'ptz' | 'thermal';
  resolution: string;
  fps: number;
}

export interface Detection {
  id: string;
  cameraId: string;
  timestamp: string;
  type: 'vehicle' | 'person' | 'object';
  confidence: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  metadata: {
    vehicleType?: string;
    color?: string;
    licensePlate?: string;
    direction?: string;
    speed?: number;
  };
  location: {
    latitude: number;
    longitude: number;
  };
}

export interface VehicleTrack {
  id: string;
  vehicleId: string;
  detections: Detection[];
  startTime: string;
  endTime: string;
  totalDistance: number;
  averageSpeed: number;
}

class MockDataService {
  private cameras: CameraLocation[] = [
    {
      id: 'cam-001',
      name: 'Main Entrance Camera',
      latitude: 37.7749,
      longitude: -122.4194,
      status: 'active',
      address: '123 Main St, San Francisco, CA',
      lastSeen: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      detectionCount: 15,
      cameraType: 'fixed',
      resolution: '1920x1080',
      fps: 30
    },
    {
      id: 'cam-002',
      name: 'Parking Lot Camera A',
      latitude: 37.7751,
      longitude: -122.4196,
      status: 'active',
      address: '125 Main St, San Francisco, CA',
      lastSeen: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      detectionCount: 8,
      cameraType: 'ptz',
      resolution: '1920x1080',
      fps: 25
    },
    {
      id: 'cam-003',
      name: 'Security Gate Camera',
      latitude: 37.7747,
      longitude: -122.4192,
      status: 'inactive',
      address: '121 Main St, San Francisco, CA',
      lastSeen: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
      detectionCount: 0,
      cameraType: 'fixed',
      resolution: '1280x720',
      fps: 20
    },
    {
      id: 'cam-004',
      name: 'Back Alley Camera',
      latitude: 37.7753,
      longitude: -122.4198,
      status: 'error',
      address: '127 Main St, San Francisco, CA',
      lastSeen: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      detectionCount: 0,
      cameraType: 'thermal',
      resolution: '640x480',
      fps: 15
    },
    {
      id: 'cam-005',
      name: 'Intersection Camera',
      latitude: 37.7745,
      longitude: -122.4190,
      status: 'active',
      address: '119 Main St, San Francisco, CA',
      lastSeen: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
      detectionCount: 23,
      cameraType: 'fixed',
      resolution: '1920x1080',
      fps: 30
    }
  ];

  private detections: Detection[] = [
    {
      id: 'det-001',
      cameraId: 'cam-001',
      timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      type: 'vehicle',
      confidence: 0.95,
      boundingBox: { x: 100, y: 150, width: 200, height: 100 },
      metadata: {
        vehicleType: 'sedan',
        color: 'blue',
        licensePlate: 'ABC123',
        direction: 'north',
        speed: 25
      },
      location: { latitude: 37.7749, longitude: -122.4194 }
    },
    {
      id: 'det-002',
      cameraId: 'cam-002',
      timestamp: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
      type: 'vehicle',
      confidence: 0.88,
      boundingBox: { x: 150, y: 200, width: 180, height: 90 },
      metadata: {
        vehicleType: 'suv',
        color: 'red',
        direction: 'south',
        speed: 15
      },
      location: { latitude: 37.7751, longitude: -122.4196 }
    },
    {
      id: 'det-003',
      cameraId: 'cam-005',
      timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      type: 'vehicle',
      confidence: 0.92,
      boundingBox: { x: 200, y: 100, width: 160, height: 80 },
      metadata: {
        vehicleType: 'truck',
        color: 'white',
        direction: 'east',
        speed: 30
      },
      location: { latitude: 37.7745, longitude: -122.4190 }
    },
    {
      id: 'det-004',
      cameraId: 'cam-001',
      timestamp: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
      type: 'person',
      confidence: 0.85,
      boundingBox: { x: 80, y: 120, width: 40, height: 120 },
      metadata: {},
      location: { latitude: 37.7749, longitude: -122.4194 }
    }
  ];

  private vehicleTracks: VehicleTrack[] = [
    {
      id: 'track-001',
      vehicleId: 'vehicle-001',
      detections: [
        {
          id: 'det-001',
          cameraId: 'cam-001',
          timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
          type: 'vehicle',
          confidence: 0.95,
          boundingBox: { x: 100, y: 150, width: 200, height: 100 },
          metadata: {
            vehicleType: 'sedan',
            color: 'blue',
            licensePlate: 'ABC123',
            direction: 'north',
            speed: 25
          },
          location: { latitude: 37.7749, longitude: -122.4194 }
        },
        {
          id: 'det-005',
          cameraId: 'cam-002',
          timestamp: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
          type: 'vehicle',
          confidence: 0.90,
          boundingBox: { x: 120, y: 160, width: 190, height: 95 },
          metadata: {
            vehicleType: 'sedan',
            color: 'blue',
            licensePlate: 'ABC123',
            direction: 'north',
            speed: 22
          },
          location: { latitude: 37.7751, longitude: -122.4196 }
        }
      ],
      startTime: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      endTime: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
      totalDistance: 0.2,
      averageSpeed: 23.5
    }
  ];

  async getCameras(): Promise<CameraLocation[]> {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
    return [...this.cameras];
  }

  async getDetections(filters?: {
    cameraId?: string;
    type?: string;
    startTime?: string;
    endTime?: string;
    limit?: number;
  }): Promise<Detection[]> {
    await new Promise(resolve => setTimeout(resolve, 300));
    
    let filtered = [...this.detections];
    
    if (filters?.cameraId) {
      filtered = filtered.filter(d => d.cameraId === filters.cameraId);
    }
    
    if (filters?.type) {
      filtered = filtered.filter(d => d.type === filters.type);
    }
    
    if (filters?.limit) {
      filtered = filtered.slice(0, filters.limit);
    }
    
    return filtered;
  }

  async getVehicleTracks(filters?: {
    vehicleId?: string;
    startTime?: string;
    endTime?: string;
  }): Promise<VehicleTrack[]> {
    await new Promise(resolve => setTimeout(resolve, 400));
    
    let filtered = [...this.vehicleTracks];
    
    if (filters?.vehicleId) {
      filtered = filtered.filter(t => t.vehicleId === filters.vehicleId);
    }
    
    return filtered;
  }

  async getCameraById(id: string): Promise<CameraLocation | null> {
    await new Promise(resolve => setTimeout(resolve, 200));
    return this.cameras.find(c => c.id === id) || null;
  }

  // Simulate real-time updates
  startRealTimeUpdates(callback: (data: { cameras: CameraLocation[], detections: Detection[] }) => void) {
    const interval = setInterval(() => {
      // Simulate status changes and new detections
      const updatedCameras = this.cameras.map(camera => ({
        ...camera,
        lastSeen: new Date().toISOString(),
        detectionCount: Math.floor(Math.random() * 30)
      }));
      
      const newDetections = this.generateRandomDetection();
      this.detections.push(newDetections);
      
      callback({
        cameras: updatedCameras,
        detections: [newDetections]
      });
    }, 10000); // Update every 10 seconds
    
    return () => clearInterval(interval);
  }

  private generateRandomDetection(): Detection {
    const camera = this.cameras[Math.floor(Math.random() * this.cameras.length)];
    const types: Detection['type'][] = ['vehicle', 'person', 'object'];
    const vehicleTypes = ['sedan', 'suv', 'truck', 'motorcycle'];
    const colors = ['red', 'blue', 'white', 'black', 'gray', 'green'];
    
    return {
      id: `det-${Date.now()}`,
      cameraId: camera.id,
      timestamp: new Date().toISOString(),
      type: types[Math.floor(Math.random() * types.length)],
      confidence: Math.random() * 0.3 + 0.7, // 0.7 to 1.0
      boundingBox: {
        x: Math.floor(Math.random() * 400),
        y: Math.floor(Math.random() * 300),
        width: Math.floor(Math.random() * 200) + 100,
        height: Math.floor(Math.random() * 100) + 50
      },
      metadata: {
        vehicleType: vehicleTypes[Math.floor(Math.random() * vehicleTypes.length)],
        color: colors[Math.floor(Math.random() * colors.length)],
        direction: ['north', 'south', 'east', 'west'][Math.floor(Math.random() * 4)],
        speed: Math.floor(Math.random() * 50) + 10
      },
      location: {
        latitude: camera.latitude + (Math.random() - 0.5) * 0.001,
        longitude: camera.longitude + (Math.random() - 0.5) * 0.001
      }
    };
  }
}

export const mockDataService = new MockDataService();