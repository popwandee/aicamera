import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import CameraStatus from './pages/CameraStatus'
import NetworkAnalysis from './pages/NetworkAnalysis'
import DetectionAnalysis from './pages/DetectionAnalysis'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/camera-status" element={<CameraStatus />} />
          <Route path="/network-analysis" element={<NetworkAnalysis />} />
          <Route path="/detection-analysis" element={<DetectionAnalysis />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App