<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Component } from 'vue'
import {
  CheckIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  CalendarDaysIcon,
  Squares2X2Icon,
  ChevronDownIcon,
} from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'

const { t, tm } = useI18n()

const faqOpen = ref<number | null>(null)

function toggleFaq(i: number) {
  faqOpen.value = faqOpen.value === i ? null : i
}

// Feature card icons — one per card; length must match marketing.features.cards
const featureIcons: Component[] = [
  UsersIcon,
  ClipboardDocumentListIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  CalendarDaysIcon,
  Squares2X2Icon,
]

type MetricItem = { value: string; label: string }
type StepItem = { title: string; description: string }
type CardItem = { title: string; description: string }
type SegmentItem = { title: string; description: string }
type PlanItem = {
  name: string
  price: string
  period: string
  tag: string
  highlight: string
  features: string[]
  cta: string
}
type FaqItem = { q: string; a: string }

const metrics = computed<MetricItem[]>(() => {
  const raw = tm('marketing.benefits.metrics')
  return Array.isArray(raw) ? (raw as MetricItem[]) : []
})

const workflowSteps = computed<StepItem[]>(() => {
  const raw = tm('marketing.workflow.steps')
  return Array.isArray(raw) ? (raw as StepItem[]) : []
})

const featureCards = computed<CardItem[]>(() => {
  const raw = tm('marketing.features.cards')
  return Array.isArray(raw) ? (raw as CardItem[]) : []
})

const trustSegments = computed<SegmentItem[]>(() => {
  const raw = tm('marketing.trust.segments')
  return Array.isArray(raw) ? (raw as SegmentItem[]) : []
})

const trustAssurances = computed<string[]>(() => {
  const raw = tm('marketing.trust.assurances')
  return Array.isArray(raw) ? (raw as string[]) : []
})

const pricingPlans = computed<PlanItem[]>(() => {
  const raw = tm('marketing.pricing.plans')
  if (!Array.isArray(raw)) return []
  return (raw as PlanItem[]).map((plan) => ({
    ...plan,
    features: Array.isArray(plan.features) ? plan.features : [],
  }))
})

const faqItems = computed<FaqItem[]>(() => {
  const raw = tm('marketing.faq.items')
  return Array.isArray(raw) ? (raw as FaqItem[]) : []
})
</script>

<template>
  <div class="min-h-screen bg-white">
    <!-- ── Sticky navigation ── -->
    <header role="banner">
      <nav
        class="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-gray-100"
        :aria-label="t('marketing.nav.mainNavigation')"
      >
        <div class="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <!-- Brand -->
          <a
            href="/"
            class="flex items-center gap-2 shrink-0"
            :aria-label="t('marketing.nav.homeLabel')"
          >
            <div
              class="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <span class="text-white text-sm font-bold">L</span>
            </div>
            <span class="text-lg font-bold text-gray-900">LeadLab</span>
          </a>

          <!-- Section anchors (hidden on very small screens) -->
          <ul class="hidden md:flex items-center gap-1 list-none m-0 p-0" role="list">
            <li
              v-for="anchor in ['product', 'workflow', 'features', 'pricing', 'faq']"
              :key="anchor"
            >
              <a
                :href="`#${anchor}`"
                class="text-sm text-gray-600 hover:text-gray-900 font-medium px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
                >{{ t(`marketing.nav.${anchor}`) }}</a
              >
            </li>
          </ul>

          <!-- Auth actions -->
          <div class="flex items-center gap-2 shrink-0">
            <a
              href="/app/login"
              class="text-sm text-gray-600 hover:text-gray-900 font-medium px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >{{ t('marketing.nav.login') }}</a
            >
            <a
              href="/app/register"
              class="text-sm bg-red-600 text-white font-semibold px-4 py-2 rounded-xl hover:bg-red-700 transition-colors"
              >{{ t('marketing.nav.getStarted') }}</a
            >
          </div>
        </div>
      </nav>
    </header>

    <main>
      <!-- ── Hero ── -->
      <section
        id="product"
        aria-labelledby="hero-heading"
        class="px-6 pt-20 pb-24 max-w-5xl mx-auto text-center"
      >
        <p class="text-sm font-semibold text-red-600 uppercase tracking-widest mb-4">
          {{ t('marketing.hero.eyebrow') }}
        </p>
        <h1
          id="hero-heading"
          class="text-5xl font-extrabold text-gray-900 mb-6 leading-tight tracking-tight"
        >
          {{ t('marketing.hero.title') }}
        </h1>
        <p class="text-xl text-gray-500 mb-10 max-w-2xl mx-auto leading-relaxed">
          {{ t('marketing.hero.subtitle') }}
        </p>
        <div class="flex flex-col sm:flex-row gap-3 justify-center mb-4">
          <a
            href="/app/register"
            class="inline-block px-8 py-3.5 bg-red-600 text-white font-semibold rounded-2xl hover:bg-red-700 transition-colors text-lg"
            >{{ t('marketing.hero.primaryCta') }}</a
          >
          <a
            href="/app/login"
            class="inline-block px-8 py-3.5 border border-gray-200 text-gray-700 font-semibold rounded-2xl hover:bg-gray-50 transition-colors text-lg"
            >{{ t('marketing.hero.secondaryCta') }}</a
          >
        </div>
        <p class="text-sm text-gray-400">{{ t('marketing.hero.note') }}</p>
      </section>

      <!-- ── Benefits / metrics ── -->
      <section id="benefits" aria-labelledby="benefits-heading" class="bg-gray-50 px-6 py-20">
        <div class="max-w-5xl mx-auto text-center">
          <h2 id="benefits-heading" class="text-3xl font-bold text-gray-900 mb-3">
            {{ t('marketing.benefits.title') }}
          </h2>
          <p class="text-gray-500 mb-12 max-w-2xl mx-auto">
            {{ t('marketing.benefits.subtitle') }}
          </p>
          <ul class="grid grid-cols-2 md:grid-cols-4 gap-6 list-none m-0 p-0" role="list">
            <li
              v-for="metric in metrics"
              :key="metric.value"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm text-center"
            >
              <div class="text-2xl font-extrabold text-red-600 mb-1">{{ metric.value }}</div>
              <div class="text-sm text-gray-500 leading-snug">{{ metric.label }}</div>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Workflow steps ── -->
      <section id="workflow" aria-labelledby="workflow-heading" class="px-6 py-20">
        <div class="max-w-5xl mx-auto">
          <h2 id="workflow-heading" class="text-3xl font-bold text-gray-900 text-center mb-14">
            {{ t('marketing.workflow.title') }}
          </h2>
          <ol
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 list-none m-0 p-0"
            role="list"
          >
            <li
              v-for="(step, i) in workflowSteps"
              :key="step.title"
              class="flex flex-col items-start gap-3"
            >
              <div
                class="w-10 h-10 rounded-full bg-red-50 border-2 border-red-200 flex items-center justify-center shrink-0"
                aria-hidden="true"
              >
                <span class="text-red-600 font-bold text-sm">{{ i + 1 }}</span>
              </div>
              <div>
                <h3 class="text-base font-semibold text-gray-900 mb-1">{{ step.title }}</h3>
                <p class="text-sm text-gray-500 leading-relaxed">{{ step.description }}</p>
              </div>
            </li>
          </ol>
        </div>
      </section>

      <!-- ── Feature cards ── -->
      <section id="features" aria-labelledby="features-heading" class="bg-gray-50 px-6 py-20">
        <div class="max-w-5xl mx-auto">
          <h2 id="features-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.features.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12">{{ t('marketing.features.subtitle') }}</p>
          <ul
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 list-none m-0 p-0"
            role="list"
          >
            <li
              v-for="(card, i) in featureCards"
              :key="card.title"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm"
            >
              <component
                :is="featureIcons[i] ?? Squares2X2Icon"
                class="w-9 h-9 mb-4 text-red-500"
                aria-hidden="true"
              />
              <h3 class="text-base font-semibold text-gray-900 mb-2">{{ card.title }}</h3>
              <p class="text-sm text-gray-500 leading-relaxed">{{ card.description }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Trust / for-whom ── -->
      <section id="trust" aria-labelledby="trust-heading" class="px-6 py-20">
        <div class="max-w-5xl mx-auto">
          <h2 id="trust-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.trust.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12">{{ t('marketing.trust.subtitle') }}</p>

          <!-- Segment cards -->
          <ul class="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-12 list-none m-0 p-0" role="list">
            <li
              v-for="seg in trustSegments"
              :key="seg.title"
              class="bg-gray-50 rounded-2xl p-6 border border-gray-100 text-center"
            >
              <h3 class="text-base font-semibold text-gray-900 mb-2">{{ seg.title }}</h3>
              <p class="text-sm text-gray-500">{{ seg.description }}</p>
            </li>
          </ul>

          <!-- Assurances -->
          <div class="bg-red-50 rounded-2xl border border-red-100 p-6 max-w-2xl mx-auto">
            <p class="text-sm font-semibold text-gray-900 mb-3">
              {{ t('marketing.trust.assurancesTitle') }}
            </p>
            <ul class="space-y-2 list-none m-0 p-0" role="list">
              <li
                v-for="assurance in trustAssurances"
                :key="assurance"
                class="flex items-center gap-2 text-sm text-gray-700"
              >
                <CheckIcon class="w-4 h-4 text-green-500 shrink-0" aria-hidden="true" />
                {{ assurance }}
              </li>
            </ul>
          </div>
        </div>
      </section>

      <!-- ── Pricing ── -->
      <section id="pricing" aria-labelledby="pricing-heading" class="bg-gray-50 px-6 py-20">
        <div class="max-w-4xl mx-auto">
          <h2 id="pricing-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.pricing.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12">{{ t('marketing.pricing.subtitle') }}</p>

          <ul class="grid grid-cols-1 md:grid-cols-2 gap-6 list-none m-0 p-0" role="list">
            <li
              v-for="plan in pricingPlans"
              :key="plan.name"
              class="rounded-2xl p-8 relative bg-white"
              :class="plan.highlight ? 'border-2 border-red-600' : 'border border-gray-200'"
            >
              <div
                v-if="plan.highlight"
                class="absolute -top-3 left-6 bg-red-600 text-white text-xs font-bold px-3 py-1 rounded-full"
                :aria-label="t('marketing.nav.popularPlanLabel')"
              >
                {{ plan.highlight }}
              </div>
              <div
                class="text-sm font-semibold uppercase tracking-wide mb-2"
                :class="plan.highlight ? 'text-red-600' : 'text-gray-500'"
              >
                {{ plan.name }}
              </div>
              <div class="text-4xl font-extrabold text-gray-900 mb-1">{{ plan.price }}</div>
              <div class="text-gray-400 text-sm mb-1">{{ plan.period }}</div>
              <div class="text-xs text-gray-400 mb-6">{{ plan.tag }}</div>
              <ul class="space-y-2.5 mb-8 list-none m-0 p-0" role="list">
                <li
                  v-for="feat in plan.features"
                  :key="feat"
                  class="flex items-center gap-2 text-sm text-gray-700"
                >
                  <CheckIcon class="w-4 h-4 text-green-500 shrink-0" aria-hidden="true" />
                  {{ feat }}
                </li>
              </ul>
              <a
                href="/app/register"
                class="block text-center px-6 py-3 rounded-xl font-medium transition-colors"
                :class="
                  plan.highlight
                    ? 'bg-red-600 text-white hover:bg-red-700'
                    : 'border border-gray-200 text-gray-700 hover:bg-gray-50'
                "
                >{{ plan.cta }}</a
              >
            </li>
          </ul>

          <p class="text-center text-sm text-gray-400 mt-6">{{ t('marketing.pricing.note') }}</p>
        </div>
      </section>

      <!-- ── Bottom CTA banner ── -->
      <section aria-labelledby="cta-heading" class="px-6 py-20">
        <div class="max-w-3xl mx-auto text-center">
          <h2 id="cta-heading" class="text-3xl font-bold text-gray-900 mb-4">
            {{ t('marketing.cta.title') }}
          </h2>
          <p class="text-gray-500 mb-8">{{ t('marketing.cta.subtitle') }}</p>
          <div class="flex flex-col sm:flex-row gap-3 justify-center">
            <a
              href="/app/register"
              class="inline-block px-8 py-3.5 bg-red-600 text-white font-semibold rounded-2xl hover:bg-red-700 transition-colors text-lg"
              >{{ t('marketing.cta.primaryCta') }}</a
            >
            <a
              :href="t('marketing.cta.contactHref')"
              class="inline-block px-8 py-3.5 border border-gray-200 text-gray-700 font-semibold rounded-2xl hover:bg-gray-50 transition-colors text-lg"
              >{{ t('marketing.cta.secondaryCta') }}</a
            >
          </div>
        </div>
      </section>

      <!-- ── FAQ ── -->
      <section id="faq" aria-labelledby="faq-heading" class="bg-gray-50 px-6 py-20">
        <div class="max-w-3xl mx-auto">
          <h2 id="faq-heading" class="text-3xl font-bold text-gray-900 text-center mb-12">
            {{ t('marketing.faq.title') }}
          </h2>
          <dl class="space-y-3">
            <div
              v-for="(item, i) in faqItems"
              :key="i"
              class="border border-gray-200 rounded-2xl overflow-hidden bg-white"
            >
              <dt>
                <button
                  :id="`faq-btn-${i}`"
                  :aria-expanded="faqOpen === i"
                  :aria-controls="`faq-panel-${i}`"
                  class="w-full flex items-center justify-between px-6 py-4 text-left text-sm font-semibold text-gray-900 hover:bg-gray-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-inset"
                  @click="toggleFaq(i)"
                >
                  <span>{{ item.q }}</span>
                  <ChevronDownIcon
                    class="w-4 h-4 text-gray-400 ml-4 shrink-0 transition-transform duration-200"
                    :class="faqOpen === i ? 'rotate-180' : ''"
                    aria-hidden="true"
                  />
                </button>
              </dt>
              <dd :id="`faq-panel-${i}`" :aria-labelledby="`faq-btn-${i}`" role="region">
                <div
                  v-show="faqOpen === i"
                  class="px-6 pb-5 pt-4 text-sm text-gray-600 leading-relaxed border-t border-gray-100"
                >
                  {{ item.a }}
                </div>
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </main>

    <!-- ── Footer ── -->
    <footer class="border-t border-gray-100 px-6 py-10" role="contentinfo">
      <div class="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
        <!-- Brand + tagline -->
        <div class="flex flex-col items-center sm:items-start gap-1">
          <div class="flex items-center gap-2">
            <div
              class="w-6 h-6 rounded-lg bg-red-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <span class="text-white text-xs font-bold">L</span>
            </div>
            <span class="text-sm font-semibold text-gray-900">{{
              t('marketing.footer.productName')
            }}</span>
          </div>
          <span class="text-xs text-gray-400">{{ t('marketing.footer.tagline') }}</span>
        </div>

        <!-- Nav links -->
        <nav aria-label="Footer navigation">
          <ul class="flex flex-wrap justify-center gap-x-6 gap-y-2 list-none m-0 p-0" role="list">
            <li>
              <a
                href="/app/login"
                class="text-sm text-gray-400 hover:text-gray-700 transition-colors"
              >
                {{ t('marketing.footer.links.login') }}
              </a>
            </li>
            <li>
              <a
                href="/app/register"
                class="text-sm text-gray-400 hover:text-gray-700 transition-colors"
              >
                {{ t('marketing.footer.links.signup') }}
              </a>
            </li>
            <li>
              <a
                href="https://github.com/JakubMusil/LeadLab"
                target="_blank"
                rel="noopener noreferrer"
                class="text-sm text-gray-400 hover:text-gray-700 transition-colors"
                >{{ t('marketing.footer.links.github') }}</a
              >
            </li>
          </ul>
        </nav>

        <!-- Copyright -->
        <p class="text-xs text-gray-400 text-center sm:text-right">
          {{ t('marketing.footer.copyright', { year: new Date().getFullYear() }) }}
        </p>
      </div>
    </footer>
  </div>
</template>
