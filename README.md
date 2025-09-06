# Analytics Dashboard

A comprehensive frontend dashboard for analytics service displaying camera edge status analysis, unified communication network analysis, and detection result analysis.

## Features

### 🎥 Camera Edge Status Analysis
- Real-time camera status monitoring
- Performance metrics (FPS, bandwidth, temperature)
- Status history tracking
- Camera configuration management
- Uptime monitoring

### 🌐 Unified Communication Network Analysis
- Network node monitoring
- Traffic analysis and visualization
- Protocol distribution
- Bandwidth utilization tracking
- Network topology visualization

### 🔍 Detection Result Analysis
- **Location-based analysis:** Detections by location with accuracy metrics
- **Time-based analysis:** Hourly detection patterns and trends
- **License plate analysis:** Vehicle tracking and authorization status
- **Detection types:** Person, vehicle, object, and face detection statistics

## Technology Stack

- **Frontend:** React 18, Vite, Tailwind CSS
- **Charts:** Recharts for data visualization
- **Icons:** Lucide React
- **Routing:** React Router DOM
- **HTTP Client:** Axios
- **Date Handling:** date-fns

## Getting Started

### Prerequisites

- Node.js 16 or higher
- npm or yarn package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd analytics-dashboard
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser and navigate to `http://localhost:3000`

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint errors

## Project Structure

```
src/
├── components/          # Reusable UI components
│   └── Layout.jsx      # Main layout with navigation
├── pages/              # Page components
│   ├── Dashboard.jsx   # Main dashboard overview
│   ├── CameraStatus.jsx # Camera status analysis
│   ├── NetworkAnalysis.jsx # Network analysis
│   └── DetectionAnalysis.jsx # Detection analysis
├── data/               # Sample data and mock data
│   └── sampleData.js   # Sample data for all components
├── services/           # API services and utilities
│   └── api.js          # API client and endpoints
├── App.jsx             # Main app component with routing
├── main.jsx            # Application entry point
└── index.css           # Global styles and Tailwind imports
```

## Dashboard Pages

### 1. Dashboard Overview
- System health summary
- Key metrics and statistics
- Quick action buttons
- Recent alerts
- System health indicator

### 2. Camera Status
- Camera list with real-time status
- Status history charts
- Camera performance metrics
- Filter and search functionality
- Camera detail modals

### 3. Network Analysis
- Network node monitoring
- Traffic analysis charts
- Protocol distribution
- Bandwidth utilization
- Node configuration

### 4. Detection Analysis
- Tabbed interface for different analysis types
- Location-based detection statistics
- Time-based detection patterns
- License plate tracking
- Detection type distribution

## Sample Data

The dashboard includes comprehensive sample data for demonstration:

- **156 cameras** with various statuses (online, offline, warning)
- **45 network nodes** with different types (switches, routers, hubs, servers)
- **1,247 total detections** across multiple locations
- **Realistic performance metrics** and historical data

## API Integration

The dashboard is designed to work with a backend API. See `API_REFERENCE.md` for complete API documentation.

### Key API Endpoints:
- Camera Status: `/api/camera-status/*`
- Network Analysis: `/api/network-analysis/*`
- Detection Analysis: `/api/detection-analysis/*`
- Dashboard: `/api/dashboard/*`

### WebSocket Support:
Real-time updates via WebSocket connection for:
- Camera status changes
- Network node updates
- New detections
- System alerts

## Responsive Design

The dashboard is fully responsive and optimized for:
- **Desktop:** Full feature set with side navigation
- **Tablet:** Collapsible navigation with touch-friendly interface
- **Mobile:** Mobile-first design with hamburger menu

## Customization

### Styling
- Uses Tailwind CSS for consistent styling
- Custom color palette defined in `tailwind.config.js`
- Responsive breakpoints and utilities

### Components
- Modular component structure for easy customization
- Reusable UI components
- Consistent design patterns

### Data
- Easy to replace sample data with real API calls
- Configurable data refresh intervals
- Support for different data formats

## Development

### Adding New Features

1. Create new components in `src/components/`
2. Add new pages in `src/pages/`
3. Update routing in `src/App.jsx`
4. Add navigation items in `src/components/Layout.jsx`

### API Integration

1. Add new API endpoints in `src/services/api.js`
2. Update sample data in `src/data/sampleData.js`
3. Implement API calls in components
4. Handle loading states and errors

### Styling

1. Use Tailwind CSS classes for styling
2. Add custom styles in `src/index.css`
3. Update color palette in `tailwind.config.js`
4. Maintain consistent design patterns

## Production Deployment

### Build for Production

```bash
npm run build
```

### Environment Variables

Create a `.env` file for production:

```env
REACT_APP_API_BASE_URL=https://your-api-domain.com/api
REACT_APP_WS_URL=wss://your-api-domain.com/ws
```

### Docker Deployment

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

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For support and questions:
- Check the API documentation in `API_REFERENCE.md`
- Review the sample data structure
- Test with the provided sample data
- Contact the development team

## Future Enhancements

- Real-time data streaming
- Advanced filtering and search
- Export functionality
- User authentication
- Role-based access control
- Advanced analytics and reporting
- Mobile app version
- Offline support