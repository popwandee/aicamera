import React from 'react'
import { Link } from 'react-router-dom'
import { 
  Camera, 
  Network, 
  Search, 
  Activity, 
  TrendingUp, 
  AlertTriangle,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { dashboardSummary } from '../data/sampleData'

const Dashboard = () => {
  const stats = [
    {
      name: 'Total Cameras',
      value: dashboardSummary.totalCameras,
      icon: Camera,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
      change: '+2.1%',
      changeType: 'positive'
    },
    {
      name: 'Online Cameras',
      value: dashboardSummary.onlineCameras,
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
      change: '+1.2%',
      changeType: 'positive'
    },
    {
      name: 'Network Nodes',
      value: dashboardSummary.networkNodes,
      icon: Network,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
      change: '+0.5%',
      changeType: 'positive'
    },
    {
      name: 'Total Detections',
      value: dashboardSummary.totalDetections.toLocaleString(),
      icon: Search,
      color: 'text-orange-600',
      bgColor: 'bg-orange-100',
      change: '+12.3%',
      changeType: 'positive'
    }
  ]

  const quickActions = [
    {
      title: 'Camera Status',
      description: 'Monitor camera health and performance',
      href: '/camera-status',
      icon: Camera,
      color: 'bg-blue-500'
    },
    {
      title: 'Network Analysis',
      description: 'Analyze network traffic and connectivity',
      href: '/network-analysis',
      icon: Network,
      color: 'bg-purple-500'
    },
    {
      title: 'Detection Analysis',
      description: 'View detection results and analytics',
      href: '/detection-analysis',
      icon: Search,
      color: 'bg-orange-500'
    }
  ]

  const recentAlerts = [
    {
      id: 1,
      type: 'warning',
      message: 'Camera CAM-003 temperature is high (55°C)',
      time: '2 minutes ago',
      icon: AlertTriangle
    },
    {
      id: 2,
      type: 'error',
      message: 'Camera CAM-004 is offline',
      time: '1 hour ago',
      icon: XCircle
    },
    {
      id: 3,
      type: 'info',
      message: 'Network node NODE-003 utilization is high (92.1%)',
      time: '3 hours ago',
      icon: Activity
    }
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Monitor your camera network, analyze detections, and track system performance
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.name} className="card">
              <div className="flex items-center">
                <div className={`flex-shrink-0 p-3 rounded-lg ${stat.bgColor}`}>
                  <Icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-4 flex-1">
                  <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                  <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
                </div>
              </div>
              <div className="mt-4 flex items-center">
                <TrendingUp className="h-4 w-4 text-green-500" />
                <span className="ml-1 text-sm text-green-600">{stat.change}</span>
                <span className="ml-1 text-sm text-gray-500">from last week</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {quickActions.map((action) => {
            const Icon = action.icon
            return (
              <Link
                key={action.title}
                to={action.href}
                className="card hover:shadow-md transition-shadow"
              >
                <div className="flex items-center">
                  <div className={`flex-shrink-0 p-3 rounded-lg ${action.color}`}>
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <div className="ml-4">
                    <h3 className="text-sm font-medium text-gray-900">{action.title}</h3>
                    <p className="text-sm text-gray-500">{action.description}</p>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      {/* Recent Alerts */}
      <div>
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Alerts</h2>
        <div className="card">
          <div className="space-y-4">
            {recentAlerts.map((alert) => {
              const Icon = alert.icon
              return (
                <div key={alert.id} className="flex items-start">
                  <div className={`flex-shrink-0 p-2 rounded-lg ${
                    alert.type === 'error' ? 'bg-red-100' :
                    alert.type === 'warning' ? 'bg-yellow-100' : 'bg-blue-100'
                  }`}>
                    <Icon className={`h-4 w-4 ${
                      alert.type === 'error' ? 'text-red-600' :
                      alert.type === 'warning' ? 'text-yellow-600' : 'text-blue-600'
                    }`} />
                  </div>
                  <div className="ml-3 flex-1">
                    <p className="text-sm text-gray-900">{alert.message}</p>
                    <p className="text-xs text-gray-500">{alert.time}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* System Health */}
      <div>
        <h2 className="text-lg font-medium text-gray-900 mb-4">System Health</h2>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-500">Overall System Health</p>
              <p className="text-2xl font-semibold text-gray-900">{dashboardSummary.systemHealth}%</p>
            </div>
            <div className="flex items-center">
              <div className="w-16 h-16 relative">
                <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-gray-200"
                    stroke="currentColor"
                    strokeWidth="3"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-green-500"
                    stroke="currentColor"
                    strokeWidth="3"
                    fill="none"
                    strokeDasharray={`${dashboardSummary.systemHealth}, 100`}
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <CheckCircle className="h-6 w-6 text-green-500" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard