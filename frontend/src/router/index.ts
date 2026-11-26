import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import QualityRecheckView from '@/views/QualityRecheckView.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    {
      path: '/quality_recheck',
      name: 'quality-recheck',
      component: QualityRecheckView,
      alias: ['/quality-review', '/quality_review'],
    },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
