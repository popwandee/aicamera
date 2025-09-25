# AI Camera Microservices Application

A comprehensive AI camera management system built with modern microservices architecture, featuring NestJS backend services, Vue.js dashboard, and real-time communication capabilities.

## 🏗️ Architecture

This project implements a microservices architecture with the following components:

### Backend Services (NestJS)
- **API Gateway** (Port 3000) - Main entry point and service orchestration
- **MQTT Service** (Port 3001) - Edge device communication and management
- **WebSocket Service** (Port 3002) - Real-time detection data handling
- **File Service** (Port 3003) - SFTP + rsync for image file management

### Frontend
- **Vue.js Dashboard** (Port 5173) - Modern web interface with real-time updates

### Infrastructure
- **PostgreSQL** (Port 5432) - Main database
- **Redis** (Port 6379) - Caching and session management
- **MQTT Broker** (Mosquitto, Port 1883) - Device communication
- **SFTP Server** (Port 2222) - File transfers

## 🚀 Features

### Device Management
- ✅ Real-time device registration via MQTT
- ✅ Device status monitoring and heartbeat tracking
- ✅ Device configuration management
- ✅ Location-based device organization

### Detection Processing
- ✅ Real-time detection data via WebSocket
- ✅ Bulk detection processing
- ✅ Detection statistics and analytics
- ✅ Confidence-based filtering

### File Management
- ✅ SFTP-based image uploads from edge devices
- ✅ Automatic thumbnail and preview generation
- ✅ File status tracking and metadata
- ✅ Storage management and cleanup

### Dashboard Features
- ✅ Real-time device status monitoring
- ✅ Detection visualization and filtering
- ✅ Image preview and management
- ✅ Interactive charts and statistics
- ✅ Responsive design with dark mode support

## 📋 Prerequisites

- **Node.js** >= 20.x LTS
- **PostgreSQL** >= 15
- **Redis** >= 7
- **Docker & Docker Compose** (recommended)

## 🛠️ Development Setup

### 1. Clone and Install Dependencies

```bash
# Install workspace dependencies
npm install

# Install dependencies for all services
npm run install:all
```

### 2. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Update the `.env` file with your configuration:

```env
# Database
DATABASE_URL="postgresql://aicamera:aicamera123@localhost:5432/aicamera"

# Redis
REDIS_URL="redis://localhost:6379"

# MQTT
MQTT_URL="mqtt://localhost:1883"

# JWT
JWT_SECRET="your-super-secure-jwt-secret"

# Service URLs
API_GATEWAY_URL="http://localhost:3000"
MQTT_SERVICE_URL="http://localhost:3001"
WEBSOCKET_SERVICE_URL="http://localhost:3002"
FILE_SERVICE_URL="http://localhost:3003"

# Dashboard
VITE_API_URL="http://localhost:3000/api"
VITE_WS_URL="ws://localhost:3002"
```

### 3. Database Setup

```bash
# Navigate to database directory
cd database

# Install dependencies
npm install

# Generate Prisma client
npm run generate

# Run migrations
npm run migrate

# Seed the database
npm run seed
```

### 4. Start Services

#### Option A: Development Mode (Individual Services)

```bash
# Terminal 1: Start infrastructure services
docker-compose up postgres redis mosquitto

# Terminal 2: API Gateway
cd services/api-gateway && npm run start:dev

# Terminal 3: MQTT Service
cd services/mqtt-service && npm run start:dev

# Terminal 4: WebSocket Service
cd services/websocket-service && npm run start:dev

# Terminal 5: File Service
cd services/file-service && npm run start:dev

# Terminal 6: Dashboard
cd dashboard && npm run dev
```

#### Option B: Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📁 Project Structure

```
/workspace/
├── services/                    # Backend microservices
│   ├── shared/                 # Shared types, interfaces, utilities
│   ├── api-gateway/           # Main API Gateway (Port 3000)
│   ├── mqtt-service/          # MQTT device communication (Port 3001)
│   ├── websocket-service/     # Real-time detection data (Port 3002)
│   └── file-service/          # File management with SFTP (Port 3003)
├── dashboard/                  # Vue.js frontend application
├── database/                   # Prisma schema and migrations
├── storage/                    # File storage directory
├── docker-compose.yml         # Docker orchestration
├── package.json              # Workspace configuration
└── README.md                 # This file
```

## 🔧 API Documentation

### API Gateway (Port 3000)
- **Swagger UI**: http://localhost:3000/docs
- **Health Check**: http://localhost:3000/health

### MQTT Service (Port 3001)
- **Swagger UI**: http://localhost:3001/docs
- **Device API**: http://localhost:3001/devices

### WebSocket Service (Port 3002)
- **Swagger UI**: http://localhost:3002/docs
- **Detection API**: http://localhost:3002/detections
- **WebSocket**: ws://localhost:3002/detection

### File Service (Port 3003)
- **Swagger UI**: http://localhost:3003/docs
- **File API**: http://localhost:3003/files
- **SFTP**: sftp://localhost:2222

## 📊 Default Credentials

### Database Seeding
The system is seeded with these default users:

- **Admin**: admin@aicamera.com / admin123
- **Operator**: operator@aicamera.com / operator123  
- **Demo**: demo@aicamera.com / demo123

### Sample Devices
- **cam-001**: Entrance Camera (Main Entrance)
- **cam-002**: Parking Lot Camera (Parking Area)
- **sensor-001**: Motion Sensor (Corridor)

## 🧪 Testing

### Edge Device Simulation

Test MQTT communication:

```bash
# Subscribe to device registrations
mosquitto_sub -h localhost -t "aicamera/device/+/register"

# Publish device registration
mosquitto_pub -h localhost -t "aicamera/device/test-cam-001/register" \
  -m '{"name":"Test Camera","type":"CAMERA","capabilities":{"video":true}}'

# Publish device heartbeat
mosquitto_pub -h localhost -t "aicamera/device/test-cam-001/heartbeat" \
  -m '{"status":"ONLINE","timestamp":"2024-01-01T12:00:00Z"}'
```

### WebSocket Testing

Test real-time detection:

```bash
# Install wscat globally
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:3002/detection

# Send device registration
{"event": "device_register", "data": {"deviceId": "test-device", "type": "camera"}}

# Send detection
{"event": "detection_new", "data": {"deviceId": "test-device", "type": "PERSON", "confidence": 0.95}}
```

### API Testing

```bash
# Health checks
curl http://localhost:3000/health
curl http://localhost:3001/health  
curl http://localhost:3002/health
curl http://localhost:3003/health

# Get devices
curl http://localhost:3001/devices

# Get detections
curl http://localhost:3002/detections/recent
```

## 📈 Monitoring

### Service Health
- **API Gateway**: http://localhost:3000/health
- **Services**: Each service exposes `/health`, `/ready`, `/live` endpoints

### Database
- **Prisma Studio**: `cd database && npm run studio`
- **Direct Connection**: Use your preferred PostgreSQL client

### Logs
```bash
# Docker logs
docker-compose logs -f [service-name]

# Individual service logs
cd services/[service-name] && npm run start:dev
```

## 🔒 Security

### Authentication
- JWT-based authentication
- Role-based access control (Admin, Operator, User)
- Session management with Redis

### Communication Security
- HTTPS/TLS for production deployments
- WebSocket over WSS in production
- MQTT with authentication (configurable)

## 🚀 Production Deployment

### Docker Production Build

```bash
# Build all services
docker-compose -f docker-compose.prod.yml build

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Variables for Production

Ensure these are properly set:

```env
NODE_ENV=production
JWT_SECRET=<strong-random-secret>
DATABASE_URL=<production-db-url>
REDIS_URL=<production-redis-url>
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Port Conflicts**: Ensure ports 3000-3003, 5173, 5432, 6379, 1883 are available
2. **Database Connection**: Verify PostgreSQL is running and credentials are correct
3. **MQTT Connection**: Check Mosquitto broker is running on port 1883
4. **WebSocket Connection**: Ensure CORS settings allow your frontend domain

### Getting Help

- Check service logs: `docker-compose logs [service-name]`
- Verify service health: `curl http://localhost:[port]/health`
- Check database connectivity: Use Prisma Studio
- Test MQTT: Use mosquitto clients for pub/sub testing

## 🎯 Roadmap

- [ ] Enhanced authentication with OAuth2/OIDC
- [ ] Advanced analytics and reporting
- [ ] Mobile application support
- [ ] Edge AI model deployment
- [ ] Multi-tenant support
- [ ] Kubernetes deployment manifests
- [ ] Enhanced security features
- [ ] Performance optimization
- [ ] Automated testing suite

---

Built with ❤️ using NestJS, Vue.js, and modern microservices architecture.