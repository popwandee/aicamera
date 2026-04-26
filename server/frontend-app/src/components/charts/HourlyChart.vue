<template>
  <div class="chart-container">
    <Bar :data="chartData" :options="chartOptions" />
  </div>
</template>

<script>
import { Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

export default {
  name: 'HourlyChart',
  components: { Bar },
  props: {
    hourlyData: { type: Array, default: () => [] },
  },
  computed: {
    chartData() {
      return {
        labels: this.hourlyData.map(h => h.label),
        datasets: [{
          label: 'Detections',
          data: this.hourlyData.map(h => h.count),
          backgroundColor: 'rgba(0,200,255,0.18)',
          borderColor: '#00c8ff',
          borderWidth: 1,
          borderRadius: 3,
          hoverBackgroundColor: 'rgba(0,200,255,0.35)',
        }],
      };
    },
    chartOptions() {
      const data = this.hourlyData;
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0d1520',
            titleColor: '#00c8ff',
            bodyColor: '#8899aa',
            borderColor: 'rgba(0,200,255,0.25)',
            borderWidth: 1,
            padding: 8,
            callbacks: {
              title: (items) => (data[items[0].dataIndex]?.label || '') + ':00',
              label: (item) => ' ' + item.raw + ' detections',
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(136,153,170,0.08)' },
            ticks: {
              color: '#8899aa',
              font: { family: 'JetBrains Mono, monospace', size: 10 },
              maxRotation: 0,
              callback: (val, idx) => idx % 4 === 0 ? (data[idx]?.label || '') : '',
            },
          },
          y: {
            grid: { color: 'rgba(136,153,170,0.08)' },
            ticks: {
              color: '#8899aa',
              font: { family: 'JetBrains Mono, monospace', size: 10 },
              precision: 0,
            },
            beginAtZero: true,
          },
        },
      };
    },
  },
};
</script>

<style scoped>
.chart-container { height: 180px; }
</style>
