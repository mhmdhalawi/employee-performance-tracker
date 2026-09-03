import { createRouter, createWebHistory, type RouteLocationGeneric } from 'vue-router'
import PerformanceDashboard from '@/components/dashboard/PerformanceDashboard.vue'
import DataInterpretationView from '@/views/DataInterpretationView.vue'
import EmployeeDetailView from '@/views/EmployeeDetailView.vue'

function legacyRootRedirect(to: RouteLocationGeneric) {
  const employeeId = Array.isArray(to.query.employee)
    ? to.query.employee[0]
    : to.query.employee

  if (employeeId) {
    return {
      name: 'employee-detail',
      params: { employeeId },
    }
  }

  if (to.query.view === 'data-interpretation')
    return { name: 'data-interpretation' }

  return true
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: PerformanceDashboard,
      meta: { title: 'Employee performance | Cedar' },
      beforeEnter: legacyRootRedirect,
    },
    {
      path: '/dashboard',
      redirect: { name: 'dashboard' },
    },
    {
      path: '/employees/:employeeId',
      name: 'employee-detail',
      component: EmployeeDetailView,
      meta: { title: 'Employee details | Cedar' },
    },
    {
      path: '/data-interpretation',
      name: 'data-interpretation',
      component: DataInterpretationView,
      meta: { title: 'Data interpretation | Cedar' },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'dashboard' },
    },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 }
  },
})

router.afterEach((to) => {
  document.title = typeof to.meta.title === 'string'
    ? to.meta.title
    : 'Cedar performance dashboard'
})

export default router
