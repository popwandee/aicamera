import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast, { POSITION } from 'vue-toastification'
import PerfectScrollbar from 'vue3-perfect-scrollbar'

import App from './App.vue'
import router from './router'

// Styles
import './assets/css/main.css'
import 'vue-toastification/dist/index.css'
import 'vue3-perfect-scrollbar/dist/vue3-perfect-scrollbar.css'

const app = createApp(App)

// Pinia store
const pinia = createPinia()
app.use(pinia)

// Router
app.use(router)

// Toast notifications
app.use(Toast, {
  position: POSITION.TOP_RIGHT,
  timeout: 5000,
  closeOnClick: true,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: true,
  draggablePercent: 0.6,
  showCloseButtonOnHover: false,
  hideProgressBar: false,
  closeButton: 'button',
  icon: true,
  rtl: false,
})

// Perfect Scrollbar
app.use(PerfectScrollbar)

app.mount('#app')