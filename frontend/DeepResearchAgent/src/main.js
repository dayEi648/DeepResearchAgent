import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// 全局样式
import './styles/design-system.css'
import './styles/animations.css'
import './styles/markdown-theme.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
