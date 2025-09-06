import React, { useState } from 'react'
import { 
  Network, 
  Wifi, 
  WifiOff, 
  AlertTriangle, 
  RefreshCw, 
  Settings,
  Activity,
  Server,
  Router,
  Hub,
  TrendingUp,
  TrendingDown
} from 'lucide-react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell,
  BarChart,
  Bar
} from 'recharts'
import { networkAnalysisData } from '../data/sampleData'

const NetworkAnalysis = () => {
  const [selectedNode, setSelectedNode] = useState(null)
  const [filter, setFilter] = useState('all')

  const getNodeIcon = (type) => {
    switch (type) {
      case 'switch':
        return <Network className="h-4 w-4" />
      case 'router':
        return <Router className="h-4 w-4" />
      case 'hub':
        return <Hub className="h-4 w-4" />
      case 'server':
        return <Server className="h-4 w-4" />
      default:
        return <Activity className="h-4 w-4" />
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'online':
        return <Wifi className="h-4 w-4 text-green-500" />
      case 'offline':
        return <WifiOff className="h-4 w-4 text-red-500" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      default:
        return <Activity className="h-4 w-4 text-gray-500" />
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

  const getUtilizationColor = (utilization) => {
    if (utilization > 90) return 'text-red-600'
    if (utilization > 70) return 'text-yellow-600'
    return 'text-green-600'
  }

  const filteredNodes = networkAnalysisData.nodes.filter(node => {
    if (filter === 'all') return true
    return node.status === filter
  })

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#6b7280']

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Network Analysis</h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitor network performance, traffic, and connectivity
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
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-blue-100">
              <Network className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Nodes</p>
              <p className="text-2xl font-semibold text-gray-900">{networkAnalysisData.summary.totalNodes}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-green-100">
              <Wifi className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Active Connections</p>
              <p className="text-2xl font-semibold text-gray-900">{networkAnalysisData.summary.activeConnections}</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-purple-100">
              <TrendingUp className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Bandwidth Utilization</p>
              <p className="text-2xl font-semibold text-gray-900">{networkAnalysisData.summary.bandwidthUtilization}%</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-orange-100">
              <Activity className="h-6 w-6 text-orange-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Latency</p>
              <p className="text-2xl font-semibold text-gray-900">{networkAnalysisData.summary.latency}ms</p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="flex-shrink-0 p-3 rounded-lg bg-red-100">
              <TrendingDown className="h-6 w-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Packet Loss</p>
              <p className="text-2xl font-semibold text-gray-900">{networkAnalysisData.summary.packetLoss}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Traffic Chart */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Network Traffic (24h)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={networkAnalysisData.trafficData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="inbound" stroke="#3b82f6" strokeWidth={2} name="Inbound (Mbps)" />
              <Line type="monotone" dataKey="outbound" stroke="#10b981" strokeWidth={2} name="Outbound (Mbps)" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Protocol Distribution */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Protocol Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={networkAnalysisData.protocolDistribution}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ protocol, percentage }) => `${protocol}: ${percentage}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="percentage"
              >
                {networkAnalysisData.protocolDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Node List */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Network Nodes</h3>
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
                  Node
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  IP Address
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Connections
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Bandwidth
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Utilization
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
              {filteredNodes.map((node) => (
                <tr key={node.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getNodeIcon(node.type)}
                      <div className="ml-3">
                        <div className="text-sm font-medium text-gray-900">{node.name}</div>
                        <div className="text-sm text-gray-500">{node.id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      {node.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getStatusIcon(node.status)}
                      <span className={`ml-2 ${getStatusBadge(node.status)}`}>
                        {node.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {node.ip}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {node.connections}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {node.bandwidth}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                        <div 
                          className={`h-2 rounded-full ${
                            node.utilization > 90 ? 'bg-red-500' : 
                            node.utilization > 70 ? 'bg-yellow-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${node.utilization}%` }}
                        ></div>
                      </div>
                      <span className={`text-sm ${getUtilizationColor(node.utilization)}`}>
                        {node.utilization}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(node.lastSeen).toLocaleTimeString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button
                      onClick={() => setSelectedNode(node)}
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

      {/* Node Detail Modal */}
      {selectedNode && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setSelectedNode(null)} />
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">{selectedNode.name}</h3>
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    ×
                  </button>
                </div>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-gray-500">Node ID</label>
                      <p className="text-sm text-gray-900">{selectedNode.id}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Type</label>
                      <p className="text-sm text-gray-900">{selectedNode.type}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Status</label>
                      <div className="flex items-center">
                        {getStatusIcon(selectedNode.status)}
                        <span className={`ml-2 ${getStatusBadge(selectedNode.status)}`}>
                          {selectedNode.status}
                        </span>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">IP Address</label>
                      <p className="text-sm text-gray-900">{selectedNode.ip}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Connections</label>
                      <p className="text-sm text-gray-900">{selectedNode.connections}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Bandwidth</label>
                      <p className="text-sm text-gray-900">{selectedNode.bandwidth}</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Utilization</label>
                      <p className="text-sm text-gray-900">{selectedNode.utilization}%</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-500">Last Seen</label>
                      <p className="text-sm text-gray-900">{new Date(selectedNode.lastSeen).toLocaleString()}</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setSelectedNode(null)}
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

export default NetworkAnalysis