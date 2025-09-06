import React, { useState } from 'react'
import { 
  Search, 
  MapPin, 
  Clock, 
  Car, 
  User, 
  Eye,
  Filter,
  Download,
  RefreshCw,
  Settings,
  AlertTriangle,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  BarChart, 
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import { detectionAnalysisData } from '../data/sampleData'

const DetectionAnalysis = () => {
  const [selectedTab, setSelectedTab] = useState('location')
  const [selectedDetection, setSelectedDetection] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')

  const getStatusIcon = (status) => {
    switch (status) {
      case 'authorized':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'unauthorized':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'suspicious':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      default:
        return <Eye className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'authorized':
        return 'status-online'
      case 'unauthorized':
        return 'status-offline'
      case 'suspicious':
        return 'status-warning'
      default:
        return 'status-offline'
    }
  }

  const filteredLicensePlates = detectionAnalysisData.licensePlateData.filter(plate =>
    plate.plate.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

  const tabs = [
    { id: 'location', name: 'Location Based', icon: MapPin },
    { id: 'time', name: 'Time Based', icon: Clock },
    { id: 'license', name: 'License Plate', icon: Car },
    { id: 'types', name: 'Detection Types', icon: Eye }
  ]

  const renderLocationBased = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Detections by Location</h3>
          <div className="space-y-4">
            {detectionAnalysisData.locationBased.map((location, index) => (
              <div key={index} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center">
                  <MapPin className="h-5 w-5 text-gray-400 mr-3" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{location.location}</p>
                    <p className="text-xs text-gray-500">
                      {location.detections} detections • {location.alerts} alerts
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{location.accuracy}%</p>
                  <p className="text-xs text-gray-500">accuracy</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Location Performance</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={detectionAnalysisData.locationBased}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="location" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="detections" fill="#3b82f6" name="Detections" />
              <Bar dataKey="alerts" fill="#ef4444" name="Alerts" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )

  const renderTimeBased = () => (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Detections by Hour (24h)</h3>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={detectionAnalysisData.timeBased}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="hour" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="detections" stroke="#3b82f6" strokeWidth={2} name="Detections" />
            <Line type="monotone" dataKey="alerts" stroke="#ef4444" strokeWidth={2} name="Alerts" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-blue-100">
              <Clock className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Peak Hour</p>
              <p className="text-lg font-semibold text-gray-900">12:00 PM</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-green-100">
              <Eye className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Max Detections</p>
              <p className="text-lg font-semibold text-gray-900">89</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-red-100">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Max Alerts</p>
              <p className="text-lg font-semibold text-gray-900">4</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  const renderLicensePlate = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div className="flex-1 max-w-lg">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search license plates..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>
        <div className="flex space-x-2">
          <button className="btn-secondary">
            <Filter className="h-4 w-4 mr-2" />
            Filter
          </button>
          <button className="btn-secondary">
            <Download className="h-4 w-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  License Plate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Detections
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  First Seen
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Seen
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Locations
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredLicensePlates.map((plate, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Car className="h-5 w-5 text-gray-400 mr-3" />
                      <div className="text-sm font-medium text-gray-900">{plate.plate}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(plate.status)}
                      <span className={`ml-2 ${getStatusBadge(plate.status)}`}>
                        {plate.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {plate.detections}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(plate.firstSeen).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(plate.lastSeen).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {plate.locations.join(', ')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button
                      onClick={() => setSelectedDetection(plate)}
                      className="text-primary-600 hover:text-primary-900 mr-3"
                    >
                      View
                    </button>
                    <button className="text-gray-600 hover:text-gray-900">
                      <Settings className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )

  const renderDetectionTypes = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Detection Types Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={detectionAnalysisData.detectionTypes}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ type, percentage }) => `${type}: ${percentage}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
              >
                {detectionAnalysisData.detectionTypes.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Detection Types Details</h3>
          <div className="space-y-4">
            {detectionAnalysisData.detectionTypes.map((type, index) => (
              <div key={index} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center">
                  <div 
                    className="w-4 h-4 rounded-full mr-3"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  ></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{type.type}</p>
                    <p className="text-xs text-gray-500">{type.count} detections</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{type.percentage}%</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Detection Analysis</h1>
          <p className="mt-1 text-sm text-gray-500">
            Analyze detection results by location, time, license plate, and type
          </p>
        </div>
        <div className="flex space-x-2">
          <button className="btn-secondary">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <button className="btn-primary">
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-blue-100">
              <Search className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Detections</p>
              <p className="text-2xl font-semibold text-gray-900">{detectionAnalysisData.summary.totalDetections.toLocaleString()}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-green-100">
              <Eye className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Today's Detections</p>
              <p className="text-2xl font-semibold text-gray-900">{detectionAnalysisData.summary.todayDetections}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-red-100">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Active Alerts</p>
              <p className="text-2xl font-semibold text-gray-900">{detectionAnalysisData.summary.activeAlerts}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-purple-100">
              <CheckCircle className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Accuracy</p>
              <p className="text-2xl font-semibold text-gray-900">{detectionAnalysisData.summary.accuracy}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setSelectedTab(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center ${
                  selectedTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4 mr-2" />
                {tab.name}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {selectedTab === 'location' && renderLocationBased()}
        {selectedTab === 'time' && renderTimeBased()}
        {selectedTab === 'license' && renderLicensePlate()}
        {selectedTab === 'types' && renderDetectionTypes()}
      </div>

      {/* Detection Detail Modal */}
      {selectedDetection && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setSelectedDetection(null)} />
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">License Plate Details</h3>
                  <button
                    onClick={() => setSelectedDetection(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    ×
                  </button>
                </div>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-gray-500">License Plate</label>
                      <p className="text-sm text-gray-900">{selectedDetection.plate}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Status</label>
                      <div className="flex items-center">
                        {getStatusIcon(selectedDetection.status)}
                        <span className={`ml-2 ${getStatusBadge(selectedDetection.status)}`}>
                          {selectedDetection.status}
                        </span>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Total Detections</label>
                      <p className="text-sm text-gray-900">{selectedDetection.detections}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">First Seen</label>
                      <p className="text-sm text-gray-900">{new Date(selectedDetection.firstSeen).toLocaleString()}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Last Seen</label>
                      <p className="text-sm text-gray-900">{new Date(selectedDetection.lastSeen).toLocaleString()}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Locations</label>
                      <p className="text-sm text-gray-900">{selectedDetection.locations.join(', ')}</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setSelectedDetection(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DetectionAnalysis