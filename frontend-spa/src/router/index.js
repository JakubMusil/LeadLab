import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useFirmStore } from '@/stores/firm';
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
                    path: 'leads',
                    component: () => import('@/views/LeadsView.vue'),
                    meta: { title: 'Leads' },
                },
                {
                    path: 'leads/:id',
                    component: () => import('@/views/LeadDetailView.vue'),
                    meta: { title: 'Lead Detail' },
                },
                {
                    path: 'leads/:id/proposals/:pid?',
                    component: () => import('@/views/ProposalBuilderView.vue'),
                    meta: { title: 'Proposal Builder' },
                },
                {
                    path: 'customers',
                    component: () => import('@/views/CustomersView.vue'),
                    meta: { title: 'Customers' },
                },
                {
                    path: 'customers/:id',
                    component: () => import('@/views/CustomerDetailView.vue'),
                    meta: { title: 'Customer Detail' },
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
                    path: 'settings',
                    component: () => import('@/views/SettingsView.vue'),
                    meta: { title: 'Settings' },
                },
                {
                    path: 'analytics',
                    component: () => import('@/views/AnalyticsView.vue'),
                    meta: { title: 'Analytics' },
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
    ],
});
router.beforeEach(async (to) => {
    const authStore = useAuthStore();
    const firmStore = useFirmStore();
    if (!authStore.initialized) {
        await authStore.init();
    }
    if (to.meta.guestOnly && authStore.user) {
        return '/app/dashboard';
    }
    if (to.meta.requiresAuth && !authStore.user) {
        return '/app/login';
    }
    if (to.meta.requiresFirm) {
        if (!firmStore.activeFirm && firmStore.firms.length === 0) {
            await firmStore.fetchFirms();
        }
        if (!firmStore.activeFirm) {
            return '/app/onboarding';
        }
    }
});
export default router;
