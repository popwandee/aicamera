# Analytics Dashboard API Reference

This document provides a comprehensive API reference for the Analytics Dashboard backend services. The API is designed to support camera edge status analysis, unified communication network analysis, and detection result analysis.

## Base URL

```
http://localhost:8000/api
```

## Authentication

All API endpoints require authentication using Bearer tokens:

```http
Authorization: Bearer <your-token>
```

## Response Format

All API responses follow a consistent format:

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": { ... }
  }
}
```

## Camera Status API

### Get Camera Status Summary

**Endpoint:** `GET /camera-status/summary`

**Description:** Retrieve overall camera status statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "total": 156,
    "online": 142,
    "offline": 8,
    "warning": 6,
    "lastUpdated": "2024-01-05T10:30:00Z"
  }
}
```

### Get All Cameras

**Endpoint:** `GET /camera-status/cameras`

**Query Parameters:**
- `status` (optional): Filter by status (`online`, `offline`, `warning`)
- `location` (optional): Filter by location
- `limit` (optional): Number of results per page (default: 50)
- `offset` (optional): Number of results to skip (default: 0)

**Response:**
```json
{
  "success": true,
  "data": {
    "cameras": [
      {
        "id": "CAM-001",
        "name": "Main Entrance Camera",
        "location": "Building A - Main Entrance",
        "status": "online",
        "lastSeen": "2024-01-05T10:28:00Z",
        "resolution": "4K",
        "fps": 30,
        "bandwidth": "15.2 Mbps",
        "temperature": 42,
        "uptime": "99.8%"
      }
    ],
    "total": 156,
    "limit": 50,
    "offset": 0
  }
}
```

### Get Specific Camera

**Endpoint:** `GET /camera-status/cameras/{cameraId}`

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "CAM-001",
    "name": "Main Entrance Camera",
    "location": "Building A - Main Entrance",
    "status": "online",
    "lastSeen": "2024-01-05T10:28:00Z",
    "resolution": "4K",
    "fps": 30,
    "bandwidth": "15.2 Mbps",
    "temperature": 42,
    "uptime": "99.8%",
    "settings": {
      "brightness": 50,
      "contrast": 50,
      "saturation": 50
    }
  }
}
```

### Get Camera Status History

**Endpoint:** `GET /camera-status/history`

**Query Parameters:**
- `cameraId` (optional): Specific camera ID
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `granularity` (optional): Data granularity (`hour`, `day`, `week`)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "date": "2024-01-01",
      "online": 150,
      "offline": 4,
      "warning": 2
    }
  ]
}
```

### Update Camera Settings

**Endpoint:** `PUT /camera-status/cameras/{cameraId}`

**Request Body:**
```json
{
  "brightness": 60,
  "contrast": 55,
  "saturation": 45
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "CAM-001",
    "settings": {
      "brightness": 60,
      "contrast": 55,
      "saturation": 45
    }
  }
}
```

### Restart Camera

**Endpoint:** `POST /camera-status/cameras/{cameraId}/restart`

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "CAM-001",
    "status": "restarting",
    "message": "Camera restart initiated"
  }
}
```

## Network Analysis API

### Get Network Summary

**Endpoint:** `GET /network-analysis/summary`

**Response:**
```json
{
  "success": true,
  "data": {
    "totalNodes": 45,
    "activeConnections": 38,
    "bandwidthUtilization": 68.5,
    "latency": 12.3,
    "packetLoss": 0.2
  }
}
```

### Get Network Nodes

**Endpoint:** `GET /network-analysis/nodes`

**Query Parameters:**
- `status` (optional): Filter by status (`online`, `offline`, `warning`)
- `type` (optional): Filter by type (`switch`, `router`, `hub`, `server`)
- `limit` (optional): Number of results per page
- `offset` (optional): Number of results to skip

**Response:**
```json
{
  "success": true,
  "data": {
    "nodes": [
      {
        "id": "NODE-001",
        "name": "Core Switch 1",
        "type": "switch",
        "status": "online",
        "ip": "192.168.1.1",
        "connections": 12,
        "bandwidth": "1 Gbps",
        "utilization": 45.2,
        "lastSeen": "2024-01-05T10:28:00Z"
      }
    ],
    "total": 45
  }
}
```

### Get Network Traffic Data

**Endpoint:** `GET /network-analysis/traffic`

**Query Parameters:**
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `granularity` (optional): Data granularity (`hour`, `day`)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "time": "00:00",
      "inbound": 120,
      "outbound": 95
    }
  ]
}
```

### Get Protocol Distribution

**Endpoint:** `GET /network-analysis/protocols`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "protocol": "HTTP/HTTPS",
      "percentage": 45.2,
      "color": "#3b82f6"
    }
  ]
}
```

### Get Network Topology

**Endpoint:** `GET /network-analysis/topology`

**Response:**
```json
{
  "success": true,
  "data": {
    "nodes": [
      {
        "id": "NODE-001",
        "name": "Core Switch 1",
        "type": "switch",
        "position": { "x": 100, "y": 100 }
      }
    ],
    "links": [
      {
        "source": "NODE-001",
        "target": "NODE-002",
        "bandwidth": "1 Gbps"
      }
    ]
  }
}
```

### Update Node Configuration

**Endpoint:** `PUT /network-analysis/nodes/{nodeId}`

**Request Body:**
```json
{
  "name": "Updated Node Name",
  "settings": {
    "bandwidth": "2 Gbps",
    "priority": "high"
  }
}
```

## Detection Analysis API

### Get Detection Summary

**Endpoint:** `GET /detection-analysis/summary`

**Response:**
```json
{
  "success": true,
  "data": {
    "totalDetections": 1247,
    "todayDetections": 89,
    "activeAlerts": 12,
    "accuracy": 94.2
  }
}
```

### Get Location-Based Detections

**Endpoint:** `GET /detection-analysis/location`

**Query Parameters:**
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `location` (optional): Specific location filter

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "location": "Main Entrance",
      "detections": 234,
      "alerts": 3,
      "accuracy": 96.1,
      "coordinates": { "lat": 40.7128, "lng": -74.0060 }
    }
  ]
}
```

### Get Time-Based Detections

**Endpoint:** `GET /detection-analysis/time`

**Query Parameters:**
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `granularity` (optional): Data granularity (`hour`, `day`, `week`)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "hour": "00:00",
      "detections": 12,
      "alerts": 1
    }
  ]
}
```

### Get License Plate Data

**Endpoint:** `GET /detection-analysis/license-plates`

**Query Parameters:**
- `plate` (optional): License plate search term
- `status` (optional): Filter by status (`authorized`, `unauthorized`, `suspicious`)
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `limit` (optional): Number of results per page
- `offset` (optional): Number of results to skip

**Response:**
```json
{
  "success": true,
  "data": {
    "plates": [
      {
        "plate": "ABC-1234",
        "detections": 15,
        "firstSeen": "2024-01-01T08:30:00Z",
        "lastSeen": "2024-01-05T17:45:00Z",
        "locations": ["Main Entrance", "Parking Lot"],
        "status": "authorized"
      }
    ],
    "total": 4
  }
}
```

### Get Detection Types

**Endpoint:** `GET /detection-analysis/types`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "type": "Person",
      "count": 456,
      "percentage": 36.6
    }
  ]
}
```

### Get Specific Detection

**Endpoint:** `GET /detection-analysis/detections/{detectionId}`

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "DET-001",
    "type": "Person",
    "timestamp": "2024-01-05T10:30:00Z",
    "location": "Main Entrance",
    "confidence": 0.95,
    "imageUrl": "/images/detections/DET-001.jpg",
    "metadata": {
      "age": "25-35",
      "gender": "male",
      "clothing": "blue shirt"
    }
  }
}
```

### Search Detections

**Endpoint:** `GET /detection-analysis/search`

**Query Parameters:**
- `q` (optional): Search query
- `type` (optional): Detection type filter
- `location` (optional): Location filter
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `confidence` (optional): Minimum confidence threshold
- `limit` (optional): Number of results per page
- `offset` (optional): Number of results to skip

**Response:**
```json
{
  "success": true,
  "data": {
    "detections": [
      {
        "id": "DET-001",
        "type": "Person",
        "timestamp": "2024-01-05T10:30:00Z",
        "location": "Main Entrance",
        "confidence": 0.95
      }
    ],
    "total": 1247
  }
}
```

### Export Detection Data

**Endpoint:** `GET /detection-analysis/export`

**Query Parameters:**
- `format` (optional): Export format (`csv`, `json`, `xlsx`)
- `startDate` (optional): Start date (ISO 8601)
- `endDate` (optional): End date (ISO 8601)
- `type` (optional): Detection type filter
- `location` (optional): Location filter

**Response:** File download (CSV, JSON, or Excel format)

## Dashboard API

### Get Dashboard Summary

**Endpoint:** `GET /dashboard/summary`

**Response:**
```json
{
  "success": true,
  "data": {
    "totalCameras": 156,
    "onlineCameras": 142,
    "networkNodes": 45,
    "totalDetections": 1247,
    "systemHealth": 94.2,
    "lastUpdate": "2024-01-05T10:30:00Z"
  }
}
```

### Get Real-Time Metrics

**Endpoint:** `GET /dashboard/metrics`

**Response:**
```json
{
  "success": true,
  "data": {
    "timestamp": "2024-01-05T10:30:00Z",
    "metrics": {
      "cameraStatus": {
        "online": 142,
        "offline": 8,
        "warning": 6
      },
      "networkHealth": {
        "bandwidthUtilization": 68.5,
        "latency": 12.3,
        "packetLoss": 0.2
      },
      "detectionStats": {
        "todayDetections": 89,
        "activeAlerts": 12,
        "accuracy": 94.2
      }
    }
  }
}
```

### Get Alerts

**Endpoint:** `GET /dashboard/alerts`

**Query Parameters:**
- `severity` (optional): Filter by severity (`low`, `medium`, `high`, `critical`)
- `status` (optional): Filter by status (`active`, `resolved`)
- `limit` (optional): Number of results per page
- `offset` (optional): Number of results to skip

**Response:**
```json
{
  "success": true,
  "data": {
    "alerts": [
      {
        "id": "ALT-001",
        "type": "camera_offline",
        "severity": "high",
        "status": "active",
        "message": "Camera CAM-004 is offline",
        "timestamp": "2024-01-05T08:30:00Z",
        "source": "CAM-004",
        "metadata": {
          "location": "Building C - Emergency Exit",
          "lastSeen": "2024-01-05T06:30:00Z"
        }
      }
    ],
    "total": 12
  }
}
```

### Get System Health

**Endpoint:** `GET /dashboard/health`

**Response:**
```json
{
  "success": true,
  "data": {
    "overall": 94.2,
    "components": {
      "cameras": 91.0,
      "network": 96.5,
      "detection": 95.0,
      "storage": 98.0
    },
    "timestamp": "2024-01-05T10:30:00Z"
  }
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Request parameters are invalid |
| `UNAUTHORIZED` | Authentication required |
| `FORBIDDEN` | Insufficient permissions |
| `NOT_FOUND` | Resource not found |
| `INTERNAL_ERROR` | Internal server error |
| `SERVICE_UNAVAILABLE` | Service temporarily unavailable |
| `RATE_LIMITED` | Too many requests |

## Rate Limiting

API requests are rate limited to prevent abuse:

- **Standard endpoints:** 1000 requests per hour per user
- **Export endpoints:** 10 requests per hour per user
- **Real-time endpoints:** 100 requests per minute per user

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Request limit per time window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets

## WebSocket Events

For real-time updates, the dashboard supports WebSocket connections:

**Connection:** `ws://localhost:8000/ws`

### Events

#### Camera Status Update
```json
{
  "type": "camera_status_update",
  "data": {
    "cameraId": "CAM-001",
    "status": "online",
    "timestamp": "2024-01-05T10:30:00Z"
  }
}
```

#### Network Node Update
```json
{
  "type": "network_node_update",
  "data": {
    "nodeId": "NODE-001",
    "utilization": 45.2,
    "timestamp": "2024-01-05T10:30:00Z"
  }
}
```

#### New Detection
```json
{
  "type": "new_detection",
  "data": {
    "id": "DET-001",
    "type": "Person",
    "location": "Main Entrance",
    "confidence": 0.95,
    "timestamp": "2024-01-05T10:30:00Z"
  }
}
```

#### Alert
```json
{
  "type": "alert",
  "data": {
    "id": "ALT-001",
    "severity": "high",
    "message": "Camera CAM-004 is offline",
    "timestamp": "2024-01-05T10:30:00Z"
  }
}
```

## Frontend-Backend Mapping

### Component to API Mapping

| Frontend Component | API Endpoints |
|-------------------|---------------|
| Dashboard | `/dashboard/summary`, `/dashboard/metrics`, `/dashboard/alerts` |
| Camera Status | `/camera-status/summary`, `/camera-status/cameras`, `/camera-status/history` |
| Network Analysis | `/network-analysis/summary`, `/network-analysis/nodes`, `/network-analysis/traffic` |
| Detection Analysis | `/detection-analysis/summary`, `/detection-analysis/location`, `/detection-analysis/time`, `/detection-analysis/license-plates` |

### Data Flow

1. **Dashboard Load:**
   - Fetch summary data from `/dashboard/summary`
   - Fetch real-time metrics from `/dashboard/metrics`
   - Fetch recent alerts from `/dashboard/alerts`

2. **Camera Status Page:**
   - Fetch camera list from `/camera-status/cameras`
   - Fetch status history from `/camera-status/history`
   - Real-time updates via WebSocket

3. **Network Analysis Page:**
   - Fetch network summary from `/network-analysis/summary`
   - Fetch nodes from `/network-analysis/nodes`
   - Fetch traffic data from `/network-analysis/traffic`
   - Fetch protocol distribution from `/network-analysis/protocols`

4. **Detection Analysis Page:**
   - Fetch detection summary from `/detection-analysis/summary`
   - Fetch location-based data from `/detection-analysis/location`
   - Fetch time-based data from `/detection-analysis/time`
   - Fetch license plate data from `/detection-analysis/license-plates`
   - Fetch detection types from `/detection-analysis/types`

### State Management

The frontend uses the following state structure:

```javascript
// Dashboard state
{
  summary: {
    totalCameras: 156,
    onlineCameras: 142,
    networkNodes: 45,
    totalDetections: 1247,
    systemHealth: 94.2
  },
  metrics: { ... },
  alerts: [ ... ]
}

// Camera status state
{
  cameras: [ ... ],
  summary: { ... },
  statusHistory: [ ... ],
  selectedCamera: null
}

// Network analysis state
{
  nodes: [ ... ],
  summary: { ... },
  trafficData: [ ... ],
  protocolDistribution: [ ... ],
  selectedNode: null
}

// Detection analysis state
{
  summary: { ... },
  locationBased: [ ... ],
  timeBased: [ ... ],
  licensePlateData: [ ... ],
  detectionTypes: [ ... ],
  selectedDetection: null
}
```

## Development Setup

### Backend Requirements

1. **Python 3.8+**
2. **FastAPI** for API framework
3. **SQLAlchemy** for database ORM
4. **Redis** for caching and real-time updates
5. **WebSocket** support for real-time communication

### Frontend Requirements

1. **Node.js 16+**
2. **React 18+**
3. **Vite** for build tool
4. **Tailwind CSS** for styling
5. **Recharts** for data visualization
6. **Axios** for HTTP requests

### Environment Variables

**Backend (.env):**
```
DATABASE_URL=postgresql://user:password@localhost/analytics_db
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=your-secret-key
API_BASE_URL=http://localhost:8000
```

**Frontend (.env):**
```
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/ws
```

## Testing

### API Testing

Use the provided Postman collection or curl commands to test the API:

```bash
# Test camera status summary
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/camera-status/summary

# Test network analysis summary
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/network-analysis/summary

# Test detection analysis summary
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/detection-analysis/summary
```

### Frontend Testing

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Run tests
npm test

# Build for production
npm run build
```

## Deployment

### Docker Deployment

**Backend Dockerfile:**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile:**
```dockerfile
FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html
```

### Production Considerations

1. **SSL/TLS** encryption for all API endpoints
2. **Rate limiting** and **DDoS protection**
3. **Database connection pooling**
4. **Caching** for frequently accessed data
5. **Monitoring** and **logging**
6. **Backup** and **disaster recovery**
7. **Load balancing** for high availability

## Support

For technical support or questions about the API:

- **Documentation:** This API reference
- **Issues:** GitHub issues repository
- **Email:** support@analytics-dashboard.com
- **Slack:** #analytics-dashboard-support