import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/MarketingView.vue') },
    { path: '/app/', redirect: '/app/dashboard' },
    {
      path: '/app/login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/app/register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/app/forgot-password',
      component: () => import('@/views/ForgotPasswordView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/app/reset-password/:uidb64/:token',
      component: () => import('@/views/ResetPasswordView.vue'),
    },
    {
      path: '/app/invite/:token',
      component: () => import('@/views/AcceptInviteView.vue'),
    },
    {
      path: '/app/onboarding',
      component: () => import('@/views/OnboardingView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/app',
      component: () => import('@/views/AppShell.vue'),
      meta: { requiresAuth: true, requiresFirm: true },
      children: [
        {
          path: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: 'Dashboard' },
        },
        {
          path: 'records',
          component: () => import('@/views/RecordsView.vue'),
          meta: { title: 'Records' },
        },
        {
          path: 'records/:id',
          component: () => import('@/views/RecordDetailView.vue'),
          meta: { title: 'Record Detail' },
        },
        {
          path: 'records/:id/proposals/:pid?',
          component: () => import('@/views/ProposalBuilderView.vue'),
          meta: { title: 'Proposal Builder' },
        },
        {
          path: 'proposals',
          component: () => import('@/views/ProposalsView.vue'),
          meta: { title: 'Nabídky' },
        },
        {
          path: 'proposals/:id',
          component: () => import('@/views/ProposalBuilderView.vue'),
          meta: { title: 'Nabídka Detail' },
        },
        {
          path: 'directory',
          component: () => import('@/views/CustomersView.vue'),
          meta: { title: 'Adresář' },
        },
        {
          path: 'directory/:id',
          component: () => import('@/views/CustomerDetailView.vue'),
          meta: { title: 'Adresář Detail' },
        },
        {
          path: 'tasks',
          component: () => import('@/views/TasksView.vue'),
          meta: { title: 'Tasks' },
        },
        {
          path: 'tasks/:id',
          component: () => import('@/views/TaskDetailView.vue'),
          meta: { title: 'Task Detail' },
        },
        {
          path: 'task-templates',
          component: () => import('@/views/TaskTemplatesView.vue'),
          meta: { title: 'Task Templates' },
        },
        {
          path: 'calendar',
          component: () => import('@/views/CalendarView.vue'),
          meta: { title: 'Calendar' },
        },
        {
          path: 'team',
          component: () => import('@/views/TeamView.vue'),
          meta: { title: 'Team' },
        },
        {
          path: 'plugins',
          component: () => import('@/views/PluginsView.vue'),
          meta: { title: 'Plugins' },
        },
        {
          path: 'proposal-templates',
          component: () => import('@/views/ProposalTemplatesView.vue'),
          meta: { title: 'Proposal Templates' },
        },
        {
          path: 'catalog',
          component: () => import('@/views/CatalogView.vue'),
          meta: { title: 'Katalog položek' },
        },
        {
          path: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { title: 'Settings' },
        },
        {
          path: 'settings/pipeline',
          component: () => import('@/views/PipelineSettingsView.vue'),
          meta: { title: 'Pipeline Settings' },
        },
        {
          path: 'analytics',
          component: () => import('@/views/AnalyticsView.vue'),
          meta: { title: 'Analytics' },
        },
        {
          path: 'sequences',
          component: () => import('@/views/SequencesView.vue'),
          meta: { title: 'Sequences' },
        },
        {
          path: 'automations',
          component: () => import('@/views/AutomationsView.vue'),
          meta: { title: 'Automations' },
        },
        {
          path: 'timesheets',
          component: () => import('@/views/TimesheetView.vue'),
          meta: { title: 'Timesheet' },
        },
        {
          path: 'reports',
          component: () => import('@/views/ReportsView.vue'),
          meta: { title: 'Reports' },
        },
        {
          path: 'documents',
          component: () => import('@/views/DocumentsView.vue'),
          meta: { title: 'Documents' },
        },
        {
          path: 'superadmin',
          component: () => import('@/views/SuperAdminView.vue'),
          meta: { title: 'Super Admin' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', component: () => import('@/views/NotFoundView.vue') },
    {
      path: '/proposals/public/:token',
      component: () => import('@/views/PublicProposalView.vue'),
    },
    {
      path: '/app/tasks/public/:token',
      component: () => import('@/views/PublicTaskView.vue'),
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  const firmStore = useFirmStore()

  if (!authStore.initialized) {
    await authStore.init()
  }

  if (to.meta.guestOnly && authStore.user) {
    return '/app/dashboard'
  }

  if (to.meta.requiresAuth && !authStore.user) {
    return '/app/login'
  }

  if (to.meta.requiresFirm) {
    if (!firmStore.activeFirm && firmStore.firms.length === 0) {
      await firmStore.fetchFirms()
    }
    if (!firmStore.activeFirm) {
      return '/app/onboarding'
    }
  }
})

export default router
