<script setup lang="ts">
import { ref } from 'vue'
import type { Component } from 'vue'
import { CheckIcon, FunnelIcon, UserGroupIcon, ChartBarIcon } from '@heroicons/vue/24/outline'

const faqOpen = ref<number | null>(null)

const features: { icon: Component; title: string; description: string }[] = [
  {
    icon: FunnelIcon,
    title: 'Lead Management',
    description: 'Track every sales opportunity through a visual kanban pipeline with customisable stages.',
  },
  {
    icon: UserGroupIcon,
    title: 'Team Collaboration',
    description: 'Invite your team, assign leads, and stay in sync with real-time notifications.',
  },
  {
    icon: ChartBarIcon,
    title: 'Analytics & Reporting',
    description: 'Understand your pipeline velocity, conversion rates, and team performance at a glance.',
  },
]

const testimonials = [
  {
    quote: 'LeadLab cut our sales cycle by 30%. The pipeline view is incredibly intuitive.',
    name: 'Sarah K.',
    role: 'Sales Director, TechCorp',
  },
  {
    quote: "We finally have one source of truth for our leads. Onboarding the team took minutes.",
    name: 'Martin V.',
    role: 'CEO, StartupHQ',
  },
  {
    quote: 'The analytics alone are worth it. We can finally see where deals are getting stuck.',
    name: 'Lucia M.',
    role: 'Revenue Operations, ScaleUp',
  },
]

const faqs = [
  {
    q: 'Is there a free plan?',
    a: 'Yes! The Free plan includes unlimited leads, 2 team members, and core CRM features. No credit card required.',
  },
  {
    q: 'How do I upgrade to Pro?',
    a: 'Go to Settings → Workspace → Billing and click "Upgrade to Pro". You can cancel anytime.',
  },
  {
    q: 'Can I import my existing contacts?',
    a: 'Absolutely. LeadLab supports CSV import during onboarding and from the Leads page at any time.',
  },
  {
    q: 'Is my data secure?',
    a: 'All data is encrypted at rest and in transit. We are GDPR-compliant and never sell your data.',
  },
  {
    q: 'Do you offer self-hosting?',
    a: 'Yes. LeadLab is open-source and ships with a Docker Compose stack. See our self-hosting docs for details.',
  },
]
</script>

<template>
  <div class="min-h-screen bg-white">
    <!-- Sticky nav -->
    <nav class="sticky top-0 z-50 bg-white/90 backdrop-blur border-b border-gray-100 px-6 py-4 flex items-center justify-between">
      <a href="/" class="flex items-center gap-2">
        <div class="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center">
          <span class="text-white text-sm font-bold">L</span>
        </div>
        <span class="text-lg font-bold text-gray-900">LeadLab</span>
      </a>
      <div class="flex items-center gap-3">
        <a href="/app/login" class="text-sm text-gray-600 hover:text-gray-900 font-medium px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
          Login
        </a>
        <a href="/app/register" class="text-sm bg-red-600 text-white font-medium px-4 py-2 rounded-xl hover:bg-red-700 transition-colors">
          Get Started
        </a>
      </div>
    </nav>

    <!-- Hero -->
    <section class="px-6 pt-20 pb-24 max-w-5xl mx-auto text-center">
      <h1 class="text-5xl font-extrabold text-gray-900 mb-6 leading-tight">
        The CRM that gets out<br class="hidden sm:block" /> of your way
      </h1>
      <p class="text-xl text-gray-500 mb-10 max-w-2xl mx-auto">
        LeadLab helps sales teams track leads, close deals, and grow revenue — without the complexity of enterprise CRMs.
      </p>
      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <a href="/app/register" class="inline-block px-8 py-3.5 bg-red-600 text-white font-semibold rounded-2xl hover:bg-red-700 transition-colors text-lg">
          Start for free
        </a>
        <a href="/app/login" class="inline-block px-8 py-3.5 border border-gray-200 text-gray-700 font-semibold rounded-2xl hover:bg-gray-50 transition-colors text-lg">
          Sign in
        </a>
      </div>
    </section>

    <!-- Features -->
    <section class="bg-gray-50 px-6 py-20">
      <div class="max-w-5xl mx-auto">
        <h2 class="text-3xl font-bold text-gray-900 text-center mb-12">Everything your team needs</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div v-for="f in features" :key="f.title" class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm">
            <component :is="f.icon" class="w-10 h-10 mb-4 text-red-500" />
            <h3 class="text-lg font-semibold text-gray-900 mb-2">{{ f.title }}</h3>
            <p class="text-gray-500 text-sm leading-relaxed">{{ f.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Pricing -->
    <section class="px-6 py-20 max-w-4xl mx-auto">
      <h2 class="text-3xl font-bold text-gray-900 text-center mb-12">Simple, transparent pricing</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Free -->
        <div class="rounded-2xl border border-gray-200 p-8">
          <div class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">Free</div>
          <div class="text-4xl font-extrabold text-gray-900 mb-1">$0</div>
          <div class="text-gray-400 text-sm mb-6">Forever free</div>
          <ul class="space-y-3 mb-8 text-sm text-gray-700">
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Unlimited leads</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Up to 2 team members</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Basic pipeline</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> CSV import</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Email support</li>
          </ul>
          <a href="/app/register" class="block text-center px-6 py-3 border border-gray-200 rounded-xl text-gray-700 font-medium hover:bg-gray-50 transition-colors">
            Get started free
          </a>
        </div>
        <!-- Pro -->
        <div class="rounded-2xl border-2 border-red-600 p-8 relative">
          <div class="absolute -top-3 left-6 bg-red-600 text-white text-xs font-bold px-3 py-1 rounded-full">POPULAR</div>
          <div class="text-sm font-medium text-red-600 uppercase tracking-wide mb-2">Pro</div>
          <div class="text-4xl font-extrabold text-gray-900 mb-1">$29</div>
          <div class="text-gray-400 text-sm mb-6">per workspace / month</div>
          <ul class="space-y-3 mb-8 text-sm text-gray-700">
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Everything in Free</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Unlimited team members</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Advanced analytics</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Custom branding</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> API access & webhooks</li>
            <li class="flex gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> Priority support</li>
          </ul>
          <a href="/app/register" class="block text-center px-6 py-3 bg-red-600 text-white rounded-xl font-medium hover:bg-red-700 transition-colors">
            Start Pro trial
          </a>
        </div>
      </div>
    </section>

    <!-- Testimonials -->
    <section class="bg-gray-50 px-6 py-20">
      <div class="max-w-5xl mx-auto">
        <h2 class="text-3xl font-bold text-gray-900 text-center mb-12">Loved by sales teams</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-for="t in testimonials" :key="t.name" class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm">
            <p class="text-gray-700 text-sm leading-relaxed mb-4">"{{ t.quote }}"</p>
            <div class="text-sm font-semibold text-gray-900">{{ t.name }}</div>
            <div class="text-xs text-gray-400">{{ t.role }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- FAQ -->
    <section class="px-6 py-20 max-w-3xl mx-auto">
      <h2 class="text-3xl font-bold text-gray-900 text-center mb-12">Frequently asked questions</h2>
      <div class="space-y-3">
        <div
          v-for="(faq, i) in faqs"
          :key="i"
          class="border border-gray-200 rounded-2xl overflow-hidden"
        >
          <button
            class="w-full flex items-center justify-between px-6 py-4 text-left text-sm font-semibold text-gray-900 hover:bg-gray-50 transition-colors"
            @click="faqOpen = faqOpen === i ? null : i"
          >
            {{ faq.q }}
            <span class="text-gray-400 ml-4 flex-shrink-0">{{ faqOpen === i ? '−' : '+' }}</span>
          </button>
          <div v-if="faqOpen === i" class="px-6 pb-4 text-sm text-gray-600 leading-relaxed border-t border-gray-100 pt-4">
            {{ faq.a }}
          </div>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-gray-100 px-6 py-10">
      <div class="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded-lg bg-red-600 flex items-center justify-center">
            <span class="text-white text-xs font-bold">L</span>
          </div>
          <span class="text-sm font-semibold text-gray-900">LeadLab</span>
        </div>
        <div class="flex gap-6 text-sm text-gray-400">
          <a href="/app/login" class="hover:text-gray-700">Login</a>
          <a href="/app/register" class="hover:text-gray-700">Sign up</a>
          <a href="https://github.com/JakubMusil/LeadLab" target="_blank" rel="noopener" class="hover:text-gray-700">GitHub</a>
        </div>
        <div class="text-xs text-gray-400">&copy; {{ new Date().getFullYear() }} LeadLab. All rights reserved.</div>
      </div>
    </footer>
  </div>
</template>
