import React, { useState } from 'react'
import { 
  Camera, 
  Wifi, 
  WifiOff, 
  AlertTriangle, 
  RefreshCw, 
  Settings,
  Thermometer,
  Activity,
  Clock
} from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { cameraStatusData } from '../data/sampleData'

const CameraStatus = () => {
  const [selectedCamera, setSelectedCamera] = useState(null)
  const [filter, setFilter] = useState('all')

  const getStatusIcon = (status) => {
    switch (status) {
      case 'online':
        return <Wifi className="h-4 w-4 text-green-500" />
      case 'offline':
        return <WifiOff className="h-4 w-4 text-red-500" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      default:
        return <Camera className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'online':
        return 'status-online'
      case 'offline':
        return 'status-offline'
      case 'warning':
        return 'status-warning'
      default:
        return 'status-offline'
    }
  }

  const filteredCameras = cameraStatusData.cameras.filter(camera => {
    if (filter === 'all') return true
    return camera.status === filter
  })

  const statusCounts = {
    online: cameraStatusData.cameras.filter(c => c.status === 'online').length,
    offline: cameraStatusData.cameras.filter(c => c.status === 'offline').length,
    warning: cameraStatusData.cameras.filter(c => c.status === 'warning').length
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Camera Status</h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitor camera health, performance, and connectivity
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
              <Camera className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Cameras</p>
              <p className="text-2xl font-semibold text-gray-900">{cameraStatusData.summary.total}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-green-100">
              <Wifi className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Online</p>
              <p className="text-2xl font-semibold text-gray-900">{statusCounts.online}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-red-100">
              <WifiOff className="h-6 w-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Offline</p>
              <p className="text-2xl font-semibold text-gray-900">{statusCounts.offline}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-yellow-100">
              <AlertTriangle className="h-6 w-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Warning</p>
              <p className="text-2xl font-semibold text-gray-900">{statusCounts.warning}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Status History Chart */}
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Status History (Last 5 Days)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={cameraStatusData.statusHistory}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="online" stroke="#10b981" strokeWidth={2} name="Online" />
            <Line type="monotone" dataKey="offline" stroke="#ef4444" strokeWidth={2} name="Offline" />
            <Line type="monotone" dataKey="warning" stroke="#f59e0b" strokeWidth={2} name="Warning" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Filter and Camera List */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Camera List</h3>
          <div className="flex space-x-2">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="all">All Status</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
              <option value="warning">Warning</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Camera
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Location
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Resolution
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  FPS
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Bandwidth
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Temperature
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Uptime
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Seen
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredCameras.map((camera) => (
                <tr key={camera.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Camera className="h-5 w-5 text-gray-400 mr-3" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">{camera.name}</div>
                        <div className="text-sm text-gray-500">{camera.id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(camera.status)}
                      <span className={`ml-2 ${getStatusBadge(camera.status)}`}>
                        {camera.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {camera.location}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {camera.resolution}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {camera.fps}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {camera.bandwidth}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Thermometer className="h-4 w-4 text-gray-400 mr-1" />
                      <span className={`text-sm ${
                        camera.temperature > 50 ? 'text-red-600' : 
                        camera.temperature > 40 ? 'text-yellow-600' : 'text-green-600'
                      }`}>
                        {camera.temperature}°C
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {camera.uptime}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="flex items-center">
                      <Clock className="h-4 w-4 text-gray-400 mr-1" />
                      {new Date(camera.lastSeen).toLocaleTimeString()}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button
                      onClick={() => setSelectedCamera(camera)}
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

      {/* Camera Detail Modal */}
      {selectedCamera && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setSelectedCamera(null)} />
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">{selectedCamera.name}</h3>
                  <button
                    onClick={() => setSelectedCamera(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    ×
                  </button>
                </div>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-gray-500">Camera ID</label>
                      <p className="text-sm text-gray-900">{selectedCamera.id}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Status</label>
                      <div className="flex items-center">
                        {getStatusIcon(selectedCamera.status)}
                        <span className={`ml-2 ${getStatusBadge(selectedCamera.status)}`}>
                          {selectedCamera.status}
                        </span>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Location</label>
                      <p className="text-sm text-gray-900">{selectedCamera.location}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Resolution</label>
                      <p className="text-sm text-gray-900">{selectedCamera.resolution}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">FPS</label>
                      <p className="text-sm text-gray-900">{selectedCamera.fps}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Bandwidth</label>
                      <p className="text-sm text-gray-900">{selectedCamera.bandwidth}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Temperature</label>
                      <p className="text-sm text-gray-900">{selectedCamera.temperature}°C</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Uptime</label>
                      <p className="text-sm text-gray-900">{selectedCamera.uptime}</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setSelectedCamera(null)}
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

export default CameraStatus