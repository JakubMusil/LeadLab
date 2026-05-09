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
  PlayCircleIcon,
  SparklesIcon,
  BoltIcon,
  RectangleGroupIcon,
  EnvelopeIcon,
  CalendarIcon,
  ArrowDownTrayIcon,
  ArrowsRightLeftIcon,
  ChatBubbleLeftRightIcon,
  StarIcon,
  DevicePhoneMobileIcon,
  ComputerDesktopIcon,
  GlobeAltIcon,
  ArrowRightIcon,
  PhoneIcon,
} from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'

const { t, tm, rt } = useI18n()

const faqOpen = ref<number | null>(null)
const annual = ref(false)

// Interactive lead-magnet quiz state. The quiz is a self-contained,
// single-choice flow driven entirely by `marketing.quiz.questions`. We
// remember each step's selection so users can navigate back and forth and
// only show the "finished" CTA card after answering the last question.
const quizStep = ref(0)
const quizAnswers = ref<Record<number, number>>({})

function selectQuizOption(i: number) {
  quizAnswers.value = { ...quizAnswers.value, [quizStep.value]: i }
}

function quizNext() {
  if (quizStep.value < quizQuestions.value.length - 1) {
    quizStep.value += 1
  } else {
    quizStep.value = quizQuestions.value.length // sentinel: finished
  }
}

function quizPrev() {
  if (quizStep.value > 0) {
    quizStep.value -= 1
  }
}

function quizRestart() {
  quizStep.value = 0
  quizAnswers.value = {}
}

function toggleFaq(i: number) {
  faqOpen.value = faqOpen.value === i ? null : i
}

const featureIconMap = {
  customers: UsersIcon,
  tasks: ClipboardDocumentListIcon,
  proposals: DocumentTextIcon,
  permissions: ShieldCheckIcon,
  agenda: CalendarDaysIcon,
  pipeline: Squares2X2Icon,
} satisfies Record<string, Component>

const benefitIconMap = {
  bolt: BoltIcon,
  sparkles: SparklesIcon,
  rectangleGroup: RectangleGroupIcon,
  shield: ShieldCheckIcon,
} satisfies Record<string, Component>

const integrationIconMap = {
  document: DocumentTextIcon,
  envelope: EnvelopeIcon,
  calendar: CalendarIcon,
  download: ArrowDownTrayIcon,
  arrows: ArrowsRightLeftIcon,
  chat: ChatBubbleLeftRightIcon,
} satisfies Record<string, Component>

const platformIconMap = {
  mobile: DevicePhoneMobileIcon,
  desktop: ComputerDesktopIcon,
  web: GlobeAltIcon,
} satisfies Record<string, Component>

type StepItem = { title: string; description: string }
type CardItem = { title: string; description: string; icon?: string }
type FeatureCardItem = { title: string; description: string; icon: Component }
type BenefitCardItem = { title: string; description: string; icon: Component }
type IntegrationItem = { label: string; icon: Component }
type SegmentItem = { title: string; description: string }
type LogoItem = string
type WhyBullet = { title: string; description: string }
type TestimonialItem = { quote: string; name: string; role: string; company: string }
type SplitStage = { name: string; count: string }
type PreviewStage = { name: string; key: string }
type FooterLink = { label: string; href: string }
type FooterColumn = { title: string; links: FooterLink[] }
type PlanItem = {
  name: string
  price: string
  priceAnnual: string
  period: string
  periodAnnual: string
  tag: string
  highlight: string
  features: string[]
  cta: string
}
type FaqItem = { q: string; a: string }
type QuizQuestion = { q: string; options: string[] }
type WebinarItem = {
  badge: string
  title: string
  day: string
  month: string
  date: string
  ctaLabel: string
  href: string
}
type PlatformItem = { name: string; sub: string; icon: Component }

function isMessageAst(value: unknown): boolean {
  // Compiled message AST resource node from @intlify/unplugin-vue-i18n looks like
  // `{ t: 0, b: { ... } }` (or `{ type: 0, body: { ... } }`). Detect it so we can
  // resolve it via rt() instead of recursing into the AST as if it were data.
  if (value === null || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  const t = v.t ?? v.type
  if (t !== 0) return false
  return 'b' in v || 'body' in v
}

function resolveMessage<T>(value: unknown): T {
  if (typeof value === 'function' || isMessageAst(value)) {
    // Compiled message function or AST node from @intlify/unplugin-vue-i18n;
    // resolve to a plain string.
    return rt(value as Parameters<typeof rt>[0]) as T
  }
  if (Array.isArray(value)) {
    return value.map((v) => resolveMessage(v)) as T
  }
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value)) {
      out[k] = resolveMessage(v)
    }
    return out as T
  }
  return value as T
}

function arr<T>(key: string): T[] {
  const raw = tm(key)
  return Array.isArray(raw) ? raw.map((v) => resolveMessage<T>(v)) : []
}

const benefitCards = computed<BenefitCardItem[]>(() =>
  arr<CardItem>('marketing.benefits.cards').map((c) => ({
    title: c.title,
    description: c.description,
    icon: (c.icon && benefitIconMap[c.icon as keyof typeof benefitIconMap]) || SparklesIcon,
  })),
)

const workflowSteps = computed<StepItem[]>(() => arr<StepItem>('marketing.workflow.steps'))

const featureCards = computed<FeatureCardItem[]>(() =>
  arr<CardItem>('marketing.features.cards').map((c) => ({
    title: c.title,
    description: c.description,
    icon: (c.icon && featureIconMap[c.icon as keyof typeof featureIconMap]) || Squares2X2Icon,
  })),
)

const featureCardsTop = computed(() => featureCards.value.slice(0, 3))
const featureCardsBottom = computed(() => featureCards.value.slice(3))

const splitStages = computed<SplitStage[]>(() => arr<SplitStage>('marketing.features.split.stages'))

const integrationItems = computed<IntegrationItem[]>(() =>
  arr<{ label: string; icon: string }>('marketing.integrations.items').map((it) => ({
    label: it.label,
    icon:
      (it.icon && integrationIconMap[it.icon as keyof typeof integrationIconMap]) || Squares2X2Icon,
  })),
)

const trustLogos = computed<LogoItem[]>(() => arr<string>('marketing.trustStrip.logos'))
const whyBullets = computed<WhyBullet[]>(() => arr<WhyBullet>('marketing.why.bullets'))
const testimonials = computed<TestimonialItem[]>(() =>
  arr<TestimonialItem>('marketing.testimonials.items'),
)
const trustSegments = computed<SegmentItem[]>(() => arr<SegmentItem>('marketing.trust.segments'))
const trustAssurances = computed<string[]>(() => arr<string>('marketing.trust.assurances'))

const pricingPlans = computed<PlanItem[]>(() =>
  arr<PlanItem>('marketing.pricing.plans').map((p) => ({
    ...p,
    features: Array.isArray(p.features) ? p.features : [],
  })),
)

const faqItems = computed<FaqItem[]>(() => arr<FaqItem>('marketing.faq.items'))

const quizQuestions = computed<QuizQuestion[]>(() => arr<QuizQuestion>('marketing.quiz.questions'))
const quizFinished = computed(
  () => quizQuestions.value.length > 0 && quizStep.value >= quizQuestions.value.length,
)
const quizCurrentQuestion = computed<QuizQuestion | null>(
  () => quizQuestions.value[quizStep.value] ?? null,
)
const quizCurrentAnswer = computed<number | undefined>(() => quizAnswers.value[quizStep.value])
const quizCanAdvance = computed(() => quizCurrentAnswer.value !== undefined)

const webinarItems = computed<WebinarItem[]>(() => arr<WebinarItem>('marketing.webinars.items'))

const platformItems = computed<PlatformItem[]>(() =>
  arr<{ name: string; sub: string; icon: string }>('marketing.platforms.items').map((it) => ({
    name: it.name,
    sub: it.sub,
    icon:
      (it.icon && platformIconMap[it.icon as keyof typeof platformIconMap]) || DevicePhoneMobileIcon,
  })),
)

const demoBullets = computed<string[]>(() => arr<string>('marketing.demo.bullets'))
const quizBullets = computed<string[]>(() => arr<string>('marketing.quiz.bullets'))

const previewStages = computed<PreviewStage[]>(() => [
  { key: 'new', name: t('marketing.hero.preview.stages.new') },
  { key: 'qualified', name: t('marketing.hero.preview.stages.qualified') },
  { key: 'proposal', name: t('marketing.hero.preview.stages.proposal') },
  { key: 'won', name: t('marketing.hero.preview.stages.won') },
])

const footerColumns = computed<FooterColumn[]>(() => {
  const keys = ['product', 'resources', 'company', 'legal']
  return keys
    .map((key) => {
      const title = t(`marketing.footer.columns.${key}.title`)
      const links = arr<FooterLink>(`marketing.footer.columns.${key}.links`)
      return { title, links }
    })
    .filter((col) => col.links.length > 0)
})
</script>

<template>
  <div class="min-h-screen bg-white">
    <!-- ── Top announcement bar ── -->
    <div
      v-if="t('marketing.announcement.text')"
      class="bg-brand-800 text-white text-xs sm:text-sm"
      role="region"
      :aria-label="t('marketing.announcement.label')"
    >
      <div
        class="max-w-6xl mx-auto px-6 py-2 flex flex-wrap items-center justify-center gap-2 text-center"
      >
        <span
          class="inline-flex items-center gap-1.5 bg-white/15 text-white font-semibold uppercase tracking-wide text-[10px] px-2 py-0.5 rounded-full"
        >
          <SparklesIcon class="w-3 h-3" aria-hidden="true" />
          {{ t('marketing.announcement.badge') }}
        </span>
        <span class="text-white/90">{{ t('marketing.announcement.text') }}</span>
        <a
          :href="t('marketing.announcement.href')"
          class="inline-flex items-center gap-1 font-semibold text-white underline-offset-2 hover:underline"
        >
          {{ t('marketing.announcement.cta') }}
          <ArrowRightIcon class="w-3.5 h-3.5" aria-hidden="true" />
        </a>
      </div>
    </div>

    <!-- ── Sticky navigation ── -->
    <header role="banner">
      <nav class="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-gray-100">
        <div class="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <a href="/" class="flex items-center gap-2 shrink-0">
            <div
              class="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center"
              aria-hidden="true"
            >
              <span class="text-white text-sm font-bold">L</span>
            </div>
            <span class="text-lg font-bold text-gray-900">LeadLab</span>
          </a>

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

          <div class="flex items-center gap-2 shrink-0">
            <LanguageSwitcher variant="nav" class="hidden sm:inline-flex" />
            <a
              href="/app/login"
              class="hidden sm:inline-block text-sm text-gray-600 hover:text-gray-900 font-medium px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >{{ t('marketing.nav.login') }}</a
            >
            <a
              href="/app/register"
              class="text-sm bg-brand-600 text-white font-semibold px-4 py-2 rounded-xl hover:bg-brand-700 transition-colors"
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
        class="relative overflow-hidden scroll-mt-24"
      >
        <div class="hero-glow" aria-hidden="true"></div>
        <div
          class="relative px-6 pt-20 pb-24 max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12 items-center"
        >
          <div class="text-center md:text-left">
            <p class="text-sm font-semibold text-brand-600 uppercase tracking-widest mb-4">
              {{ t('marketing.hero.eyebrow') }}
            </p>
            <h1
              id="hero-heading"
              class="text-4xl sm:text-5xl font-extrabold text-gray-900 mb-6 leading-tight tracking-tight"
            >
              {{ t('marketing.hero.title') }}
            </h1>
            <p class="text-lg text-gray-500 mb-8 leading-relaxed max-w-xl md:mx-0 mx-auto">
              {{ t('marketing.hero.subtitle') }}
            </p>

            <form
              method="get"
              action="/app/register"
              class="flex flex-col sm:flex-row gap-3 mb-3 max-w-lg md:mx-0 mx-auto"
            >
              <label for="hero-email" class="sr-only">{{ t('marketing.hero.emailLabel') }}</label>
              <input
                id="hero-email"
                type="email"
                name="email"
                required
                inputmode="email"
                autocomplete="email"
                :placeholder="t('marketing.hero.emailPlaceholder')"
                :aria-label="t('marketing.hero.emailLabel')"
                class="flex-1 px-4 py-3 rounded-2xl border border-gray-200 bg-white text-gray-900 placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              />
              <button
                type="submit"
                class="px-6 py-3 bg-brand-600 text-white font-semibold rounded-2xl hover:bg-brand-700 transition-colors"
              >
                {{ t('marketing.hero.emailCta') }}
              </button>
            </form>

            <div
              class="flex flex-wrap items-center gap-x-5 gap-y-2 mb-4 justify-center md:justify-start"
            >
              <a
                href="#workflow"
                class="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900"
              >
                <PlayCircleIcon class="w-5 h-5 text-brand-500" aria-hidden="true" />
                {{ t('marketing.hero.tour') }}
              </a>
              <span class="text-xs text-gray-400">{{ t('marketing.hero.note') }}</span>
            </div>

            <p class="text-sm text-gray-500 max-w-xl md:mx-0 mx-auto">
              {{ t('marketing.hero.socialProof') }}
            </p>

            <div
              class="mt-4 flex items-center gap-2 justify-center md:justify-start"
              :aria-label="t('marketing.hero.rating.label')"
            >
              <span class="inline-flex" aria-hidden="true">
                <StarIcon
                  v-for="n in 5"
                  :key="n"
                  class="w-4 h-4 text-accent-500 fill-current"
                />
              </span>
              <span class="text-sm font-semibold text-gray-700">
                {{ t('marketing.hero.rating.score') }}
              </span>
              <span class="text-sm text-gray-500">·</span>
              <span class="text-sm text-gray-500">{{ t('marketing.hero.rating.text') }}</span>
            </div>
          </div>

          <!-- Tailwind-only product preview mock -->
          <div class="relative" aria-hidden="true">
            <div
              class="bg-white border border-gray-200 rounded-2xl shadow-sm p-5 md:p-6 max-w-md md:ml-auto"
            >
              <div class="flex items-center justify-between mb-4">
                <span
                  class="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 bg-brand-50 border border-brand-100 px-2 py-1 rounded-full"
                >
                  <span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span>
                  {{ t('marketing.hero.preview.badge') }}
                </span>
                <span class="text-xs text-gray-400 font-medium">
                  {{ t('marketing.hero.preview.stage') }}
                </span>
              </div>
              <div class="text-base font-semibold text-gray-900 mb-4">
                {{ t('marketing.hero.preview.name') }}
              </div>
              <dl class="grid grid-cols-3 gap-3 text-sm mb-5">
                <div>
                  <dt class="text-xs text-gray-400 mb-1">
                    {{ t('marketing.hero.preview.owner') }}
                  </dt>
                  <dd class="font-medium text-gray-700">
                    {{ t('marketing.hero.preview.ownerName') }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-gray-400 mb-1">
                    {{ t('marketing.hero.preview.value') }}
                  </dt>
                  <dd class="font-medium text-gray-700">
                    {{ t('marketing.hero.preview.valueAmount') }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-gray-400 mb-1">
                    {{ t('marketing.hero.preview.nextStep') }}
                  </dt>
                  <dd class="font-medium text-gray-700">
                    {{ t('marketing.hero.preview.nextStepText') }}
                  </dd>
                </div>
              </dl>
              <div class="border-t border-gray-100 pt-4">
                <div class="text-xs font-semibold text-gray-500 mb-3">
                  {{ t('marketing.hero.preview.pipelineTitle') }}
                </div>
                <div class="grid grid-cols-4 gap-1.5">
                  <div
                    v-for="(stage, idx) in previewStages"
                    :key="stage.key"
                    class="text-[10px] font-medium text-gray-500 text-center"
                  >
                    <div
                      class="h-1.5 rounded-full mb-1"
                      :class="idx <= 2 ? 'bg-brand-500' : 'bg-gray-200'"
                    ></div>
                    {{ stage.name }}
                  </div>
                </div>
              </div>
            </div>
            <div
              class="hero-floating absolute -bottom-4 -left-4 hidden sm:flex items-center gap-2 bg-white border border-gray-200 rounded-xl shadow-sm px-3 py-2 text-xs font-semibold text-gray-700"
            >
              <BoltIcon class="w-4 h-4 text-brand-500" aria-hidden="true" />
              <span>+12%</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Trust strip ── -->
      <section
        id="trust-strip"
        aria-labelledby="trust-strip-heading"
        class="px-6 py-12 border-y border-gray-100 bg-gray-50 scroll-mt-24"
      >
        <div class="max-w-6xl mx-auto">
          <p id="trust-strip-heading" class="text-center text-sm text-gray-500 font-medium mb-6">
            {{ t('marketing.trustStrip.trustedBy') }}
          </p>
          <ul
            class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 list-none m-0 p-0"
            role="list"
          >
            <li
              v-for="logo in trustLogos"
              :key="logo"
              class="flex items-center justify-center bg-white border border-gray-200 rounded-xl px-3 py-3 text-xs font-semibold text-gray-400 tracking-wide uppercase text-center"
            >
              {{ logo }}
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Benefits (outcome cards) ── -->
      <section id="benefits" aria-labelledby="benefits-heading" class="px-6 py-20 scroll-mt-24">
        <div class="max-w-6xl mx-auto">
          <h2 id="benefits-heading" class="text-3xl font-bold text-gray-900 mb-3 text-center">
            {{ t('marketing.benefits.title') }}
          </h2>
          <p class="text-gray-500 mb-12 max-w-2xl mx-auto text-center">
            {{ t('marketing.benefits.subtitle') }}
          </p>
          <ul
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 list-none m-0 p-0"
            role="list"
          >
            <li
              v-for="card in benefitCards"
              :key="card.title"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover-lift"
            >
              <component :is="card.icon" class="w-9 h-9 mb-4 text-brand-500" aria-hidden="true" />
              <h3 class="text-base font-semibold text-gray-900 mb-2">{{ card.title }}</h3>
              <p class="text-sm text-gray-500 leading-relaxed">{{ card.description }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Workflow steps ── -->
      <section
        id="workflow"
        aria-labelledby="workflow-heading"
        class="bg-gray-50 px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-6xl mx-auto">
          <h2 id="workflow-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.workflow.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-14 max-w-2xl mx-auto">
            {{ t('marketing.workflow.subtitle') }}
          </p>
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
                class="w-10 h-10 rounded-full bg-brand-50 border-2 border-brand-200 flex items-center justify-center shrink-0"
                aria-hidden="true"
              >
                <span class="text-brand-600 font-bold text-sm">{{ i + 1 }}</span>
              </div>
              <div>
                <h3 class="text-base font-semibold text-gray-900 mb-1">{{ step.title }}</h3>
                <p class="text-sm text-gray-500 leading-relaxed">{{ step.description }}</p>
              </div>
            </li>
          </ol>
        </div>
      </section>

      <!-- ── Features ── -->
      <section id="features" aria-labelledby="features-heading" class="px-6 py-20 scroll-mt-24">
        <div class="max-w-6xl mx-auto">
          <h2 id="features-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.features.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12 max-w-2xl mx-auto">
            {{ t('marketing.features.subtitle') }}
          </p>

          <ul
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 list-none m-0 p-0 mb-12"
            role="list"
          >
            <li
              v-for="card in featureCardsTop"
              :key="card.title"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover-lift"
            >
              <component :is="card.icon" class="w-9 h-9 mb-4 text-brand-500" aria-hidden="true" />
              <h3 class="text-base font-semibold text-gray-900 mb-2">{{ card.title }}</h3>
              <p class="text-sm text-gray-500 leading-relaxed">{{ card.description }}</p>
            </li>
          </ul>

          <!-- Split feature block -->
          <div
            class="grid grid-cols-1 md:grid-cols-2 gap-8 items-center bg-gray-50 border border-gray-100 rounded-2xl p-8 mb-12"
          >
            <div>
              <p class="text-sm font-semibold text-brand-600 uppercase tracking-widest mb-3">
                {{ t('marketing.features.split.eyebrow') }}
              </p>
              <h3 class="text-2xl font-bold text-gray-900 mb-3">
                {{ t('marketing.features.split.title') }}
              </h3>
              <p class="text-gray-500 leading-relaxed">
                {{ t('marketing.features.split.description') }}
              </p>
            </div>
            <div
              class="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm"
              aria-hidden="true"
            >
              <div class="grid grid-cols-4 gap-2 mb-4">
                <div
                  v-for="(stage, idx) in splitStages"
                  :key="stage.name"
                  class="rounded-xl border border-gray-100 p-2.5 text-center bg-gray-50"
                >
                  <div
                    class="text-[10px] font-semibold uppercase tracking-wide mb-1"
                    :class="idx === 2 ? 'text-brand-600' : 'text-gray-500'"
                  >
                    {{ stage.name }}
                  </div>
                  <div class="text-lg font-bold text-gray-900">{{ stage.count }}</div>
                </div>
              </div>
              <div class="flex items-center justify-between border-t border-gray-100 pt-3 text-sm">
                <span class="text-gray-500">{{ t('marketing.features.split.totalLabel') }}</span>
                <span class="font-bold text-gray-900">
                  {{ t('marketing.features.split.totalValue') }}
                </span>
              </div>
            </div>
          </div>

          <ul
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 list-none m-0 p-0"
            role="list"
          >
            <li
              v-for="card in featureCardsBottom"
              :key="card.title"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover-lift"
            >
              <component :is="card.icon" class="w-9 h-9 mb-4 text-brand-500" aria-hidden="true" />
              <h3 class="text-base font-semibold text-gray-900 mb-2">{{ card.title }}</h3>
              <p class="text-sm text-gray-500 leading-relaxed">{{ card.description }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Integrations ── -->
      <section
        id="integrations"
        aria-labelledby="integrations-heading"
        class="bg-gray-50 px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-5xl mx-auto text-center">
          <h2 id="integrations-heading" class="text-3xl font-bold text-gray-900 mb-3">
            {{ t('marketing.integrations.title') }}
          </h2>
          <p class="text-gray-500 mb-10 max-w-2xl mx-auto">
            {{ t('marketing.integrations.subtitle') }}
          </p>
          <ul class="flex flex-wrap justify-center gap-3 list-none m-0 p-0" role="list">
            <li
              v-for="item in integrationItems"
              :key="item.label"
              class="inline-flex items-center gap-2 bg-white border border-gray-200 rounded-2xl px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm"
            >
              <component :is="item.icon" class="w-4 h-4 text-brand-500" aria-hidden="true" />
              {{ item.label }}
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Why LeadLab ── -->
      <section id="why" aria-labelledby="why-heading" class="px-6 py-20 scroll-mt-24">
        <div class="max-w-5xl mx-auto">
          <h2 id="why-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.why.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12 max-w-2xl mx-auto">
            {{ t('marketing.why.subtitle') }}
          </p>
          <ul class="grid grid-cols-1 md:grid-cols-3 gap-6 list-none m-0 p-0" role="list">
            <li
              v-for="bullet in whyBullets"
              :key="bullet.title"
              class="rounded-2xl p-6 border border-gray-100 bg-white shadow-sm"
            >
              <div class="flex items-center gap-2 mb-3">
                <CheckIcon class="w-5 h-5 text-accent-500 shrink-0" aria-hidden="true" />
                <h3 class="text-base font-semibold text-gray-900">{{ bullet.title }}</h3>
              </div>
              <p class="text-sm text-gray-500 leading-relaxed">{{ bullet.description }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Quiz / lead magnet ── -->
      <section
        id="quiz"
        aria-labelledby="quiz-heading"
        class="bg-brand-50 px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
          <div>
            <p class="text-sm font-semibold text-brand-700 uppercase tracking-widest mb-3">
              {{ t('marketing.quiz.eyebrow') }}
            </p>
            <h2 id="quiz-heading" class="text-3xl font-bold text-gray-900 mb-3">
              {{ t('marketing.quiz.title') }}
            </h2>
            <p class="text-gray-600 leading-relaxed mb-6">
              {{ t('marketing.quiz.subtitle') }}
            </p>
            <ul class="space-y-2.5 list-none m-0 p-0" role="list">
              <li
                v-for="bullet in quizBullets"
                :key="bullet"
                class="flex items-start gap-2 text-sm text-gray-700"
              >
                <CheckIcon class="w-4 h-4 text-accent-500 shrink-0 mt-0.5" aria-hidden="true" />
                <span>{{ bullet }}</span>
              </li>
            </ul>
          </div>

          <div
            class="bg-white rounded-2xl p-6 md:p-7 border border-gray-100 shadow-sm"
            aria-live="polite"
          >
            <!-- Active question -->
            <template v-if="!quizFinished && quizCurrentQuestion">
              <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                  {{
                    t('marketing.quiz.progressLabel', {
                      current: quizStep + 1,
                      total: quizQuestions.length,
                    })
                  }}
                </span>
                <div
                  class="flex gap-1"
                  :aria-label="
                    t('marketing.quiz.progressLabel', {
                      current: quizStep + 1,
                      total: quizQuestions.length,
                    })
                  "
                >
                  <span
                    v-for="(_, i) in quizQuestions"
                    :key="i"
                    class="h-1.5 w-6 rounded-full"
                    :class="i <= quizStep ? 'bg-brand-600' : 'bg-gray-200'"
                    aria-hidden="true"
                  ></span>
                </div>
              </div>
              <p class="text-base font-semibold text-gray-900 mb-4">
                {{ quizCurrentQuestion.q }}
              </p>
              <ul class="space-y-2 list-none m-0 p-0 mb-5" role="list">
                <li
                  v-for="(opt, i) in quizCurrentQuestion.options"
                  :key="i"
                >
                  <button
                    type="button"
                    class="w-full text-left text-sm font-medium px-4 py-3 rounded-xl border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    :class="
                      quizCurrentAnswer === i
                        ? 'border-brand-600 bg-brand-50 text-brand-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:border-brand-300 hover:bg-brand-50'
                    "
                    :aria-pressed="quizCurrentAnswer === i"
                    @click="selectQuizOption(i)"
                  >
                    {{ opt }}
                  </button>
                </li>
              </ul>
              <div class="flex items-center justify-between">
                <button
                  type="button"
                  class="text-sm font-semibold text-gray-500 hover:text-gray-900 disabled:opacity-40 disabled:hover:text-gray-500"
                  :disabled="quizStep === 0"
                  @click="quizPrev"
                >
                  ← {{ t('marketing.quiz.prevLabel') }}
                </button>
                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 text-sm font-semibold px-4 py-2 rounded-xl bg-brand-600 text-white hover:bg-brand-700 transition-colors disabled:opacity-40 disabled:hover:bg-brand-600"
                  :disabled="!quizCanAdvance"
                  @click="quizNext"
                >
                  {{
                    quizStep === quizQuestions.length - 1
                      ? t('marketing.quiz.finishLabel')
                      : t('marketing.quiz.nextLabel')
                  }}
                  <ArrowRightIcon class="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </template>

            <!-- Finished state -->
            <template v-else>
              <div class="text-center py-2">
                <div
                  class="w-12 h-12 mx-auto rounded-full bg-accent-100 flex items-center justify-center mb-4"
                  aria-hidden="true"
                >
                  <CheckIcon class="w-6 h-6 text-accent-700" />
                </div>
                <h3 class="text-lg font-bold text-gray-900 mb-2">
                  {{ t('marketing.quiz.finishedTitle') }}
                </h3>
                <p class="text-sm text-gray-600 mb-6 max-w-xs mx-auto">
                  {{ t('marketing.quiz.finishedText') }}
                </p>
                <div class="flex flex-col sm:flex-row gap-2 justify-center">
                  <a
                    :href="t('marketing.quiz.finishedHref')"
                    class="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-xl bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 transition-colors"
                  >
                    {{ t('marketing.quiz.finishedCta') }}
                    <ArrowRightIcon class="w-4 h-4" aria-hidden="true" />
                  </a>
                  <button
                    type="button"
                    class="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-xl border border-gray-200 text-gray-700 text-sm font-semibold hover:bg-gray-50 transition-colors"
                    @click="quizRestart"
                  >
                    {{ t('marketing.quiz.restartLabel') }}
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- TODO: replace with real customer quotes -->
      <section
        id="testimonials"
        aria-labelledby="testimonials-heading"
        class="bg-gray-50 px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-6xl mx-auto">
          <h2 id="testimonials-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.testimonials.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12 max-w-2xl mx-auto">
            {{ t('marketing.testimonials.subtitle') }}
          </p>
          <ul class="grid grid-cols-1 md:grid-cols-3 gap-6 list-none m-0 p-0" role="list">
            <li
              v-for="item in testimonials"
              :key="item.name"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm flex flex-col"
            >
              <blockquote class="text-sm text-gray-700 leading-relaxed mb-5 flex-1">
                “{{ item.quote }}”
              </blockquote>
              <div class="flex items-center gap-3 border-t border-gray-100 pt-4">
                <div
                  class="w-9 h-9 rounded-full bg-brand-50 border border-brand-100 flex items-center justify-center text-xs font-bold text-brand-600 shrink-0"
                  aria-hidden="true"
                >
                  {{ item.name.charAt(0) }}
                </div>
                <div>
                  <div class="text-sm font-semibold text-gray-900">{{ item.name }}</div>
                  <div class="text-xs text-gray-500">{{ item.role }} · {{ item.company }}</div>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Webinars / events ── -->
      <section
        v-if="webinarItems.length > 0"
        id="webinars"
        aria-labelledby="webinars-heading"
        class="px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-6xl mx-auto">
          <div class="flex items-end justify-between gap-4 mb-10 flex-wrap">
            <div>
              <p class="text-sm font-semibold text-brand-700 uppercase tracking-widest mb-3">
                {{ t('marketing.webinars.eyebrow') }}
              </p>
              <h2 id="webinars-heading" class="text-3xl font-bold text-gray-900 mb-2">
                {{ t('marketing.webinars.title') }}
              </h2>
              <p class="text-gray-500 max-w-xl">
                {{ t('marketing.webinars.subtitle') }}
              </p>
            </div>
            <a
              :href="t('marketing.webinars.viewAllHref')"
              class="inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:text-brand-800"
            >
              {{ t('marketing.webinars.viewAll') }}
              <ArrowRightIcon class="w-4 h-4" aria-hidden="true" />
            </a>
          </div>

          <ul class="grid grid-cols-1 md:grid-cols-2 gap-6 list-none m-0 p-0" role="list">
            <li
              v-for="item in webinarItems"
              :key="item.title"
              class="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm flex items-center gap-5 hover-lift"
            >
              <div
                class="shrink-0 w-16 h-16 rounded-2xl bg-brand-50 border border-brand-100 flex flex-col items-center justify-center"
                aria-hidden="true"
              >
                <span class="text-[10px] font-bold uppercase text-brand-700 tracking-wide">
                  {{ item.month }}
                </span>
                <span class="text-2xl font-extrabold text-brand-700 leading-none">
                  {{ item.day }}
                </span>
              </div>
              <div class="flex-1 min-w-0">
                <span
                  class="inline-block text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full bg-accent-100 text-accent-700 mb-1.5"
                >
                  {{ item.badge }}
                </span>
                <h3 class="text-base font-semibold text-gray-900 mb-1 truncate">
                  {{ item.title }}
                </h3>
                <p class="text-xs text-gray-500">{{ item.date }}</p>
              </div>
              <a
                :href="item.href"
                class="shrink-0 inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:text-brand-800"
              >
                {{ item.ctaLabel }}
                <ArrowRightIcon class="w-4 h-4" aria-hidden="true" />
              </a>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Online demo / book a call ── -->
      <section
        id="demo"
        aria-labelledby="demo-heading"
        class="bg-brand-50 px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
          <div>
            <p class="text-sm font-semibold text-brand-700 uppercase tracking-widest mb-3">
              {{ t('marketing.demo.eyebrow') }}
            </p>
            <h2 id="demo-heading" class="text-3xl font-bold text-gray-900 mb-3">
              {{ t('marketing.demo.title') }}
            </h2>
            <p class="text-gray-600 leading-relaxed mb-6">
              {{ t('marketing.demo.subtitle') }}
            </p>
            <ul class="space-y-2.5 mb-6 list-none m-0 p-0" role="list">
              <li
                v-for="bullet in demoBullets"
                :key="bullet"
                class="flex items-start gap-2 text-sm text-gray-700"
              >
                <CheckIcon class="w-4 h-4 text-accent-500 shrink-0 mt-0.5" aria-hidden="true" />
                <span>{{ bullet }}</span>
              </li>
            </ul>
            <p class="text-sm text-gray-500">
              {{ t('marketing.demo.contactPrefix') }}
              <a
                :href="`mailto:${t('marketing.demo.contactEmail')}`"
                class="font-semibold text-brand-700 hover:underline"
                >{{ t('marketing.demo.contactEmail') }}</a
              >
              <span> · </span>
              <a
                :href="t('marketing.demo.contactPhoneHref')"
                class="inline-flex items-center gap-1 font-semibold text-brand-700 hover:underline"
              >
                <PhoneIcon class="w-3.5 h-3.5" aria-hidden="true" />
                {{ t('marketing.demo.contactPhone') }}
              </a>
            </p>
          </div>

          <div class="bg-white rounded-2xl p-6 md:p-8 border border-gray-100 shadow-sm">
            <!-- Team placeholder banner — pure CSS gradient, no photos -->
            <div
              class="rounded-2xl mb-6 h-28 relative overflow-hidden border border-brand-100"
              aria-hidden="true"
            >
              <div
                class="absolute inset-0 bg-gradient-to-br from-brand-500 via-brand-600 to-accent-500"
              ></div>
              <div class="absolute inset-0 flex items-center justify-center gap-3">
                <div
                  v-for="initial in ['A', 'M', 'J', 'K']"
                  :key="initial"
                  class="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center text-brand-700 font-bold border-2 border-white shadow"
                >
                  {{ initial }}
                </div>
              </div>
            </div>
            <form
              method="get"
              action="/app/register"
              class="space-y-3"
              :aria-label="t('marketing.demo.title')"
            >
              <div>
                <label for="demo-name" class="sr-only">{{ t('marketing.demo.formName') }}</label>
                <input
                  id="demo-name"
                  type="text"
                  name="name"
                  autocomplete="name"
                  required
                  :placeholder="t('marketing.demo.formName')"
                  class="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-900 placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                />
              </div>
              <div>
                <label for="demo-email" class="sr-only">{{ t('marketing.demo.formEmail') }}</label>
                <input
                  id="demo-email"
                  type="email"
                  name="email"
                  autocomplete="email"
                  required
                  inputmode="email"
                  :placeholder="t('marketing.demo.formEmail')"
                  class="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-900 placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                />
              </div>
              <div>
                <label for="demo-company" class="sr-only">
                  {{ t('marketing.demo.formCompany') }}
                </label>
                <input
                  id="demo-company"
                  type="text"
                  name="company"
                  autocomplete="organization"
                  :placeholder="t('marketing.demo.formCompany')"
                  class="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-gray-900 placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                />
              </div>
              <button
                type="submit"
                class="w-full px-6 py-3 bg-brand-600 text-white font-semibold rounded-xl hover:bg-brand-700 transition-colors"
              >
                {{ t('marketing.demo.formSubmit') }}
              </button>
              <p class="text-xs text-gray-400 text-center">
                {{ t('marketing.demo.note') }}
              </p>
            </form>
          </div>
        </div>
      </section>

      <!-- ── Platform availability ── -->
      <section
        id="platforms"
        aria-labelledby="platforms-heading"
        class="px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-5xl mx-auto text-center">
          <h2 id="platforms-heading" class="text-3xl font-bold text-gray-900 mb-3">
            {{ t('marketing.platforms.title') }}
          </h2>
          <p class="text-gray-500 mb-12 max-w-2xl mx-auto">
            {{ t('marketing.platforms.subtitle') }}
          </p>
          <ul
            class="grid grid-cols-2 sm:grid-cols-4 gap-4 list-none m-0 p-0"
            role="list"
          >
            <li
              v-for="item in platformItems"
              :key="item.name"
              class="bg-white rounded-2xl border border-gray-100 shadow-sm px-4 py-6 flex flex-col items-center gap-2 hover-lift"
            >
              <component :is="item.icon" class="w-8 h-8 text-brand-600" aria-hidden="true" />
              <span class="text-sm font-semibold text-gray-900">{{ item.name }}</span>
              <span class="text-xs text-gray-500">{{ item.sub }}</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- ── Trust segments ── -->
      <section id="trust" aria-labelledby="trust-heading" class="px-6 py-20 scroll-mt-24">
        <div class="max-w-5xl mx-auto">
          <h2 id="trust-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.trust.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-12">
            {{ t('marketing.trust.subtitle') }}
          </p>

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

          <div class="bg-brand-50 rounded-2xl border border-brand-100 p-6 max-w-2xl mx-auto">
            <p class="text-sm font-semibold text-gray-900 mb-3">
              {{ t('marketing.trust.assurancesTitle') }}
            </p>
            <ul class="space-y-2 list-none m-0 p-0" role="list">
              <li
                v-for="assurance in trustAssurances"
                :key="assurance"
                class="flex items-center gap-2 text-sm text-gray-700"
              >
                <CheckIcon class="w-4 h-4 text-accent-500 shrink-0" aria-hidden="true" />
                {{ assurance }}
              </li>
            </ul>
          </div>
        </div>
      </section>

      <!-- ── Pricing ── -->
      <section
        id="pricing"
        aria-labelledby="pricing-heading"
        class="bg-gray-50 px-6 py-20 scroll-mt-24"
      >
        <div class="max-w-4xl mx-auto">
          <h2 id="pricing-heading" class="text-3xl font-bold text-gray-900 text-center mb-3">
            {{ t('marketing.pricing.title') }}
          </h2>
          <p class="text-gray-500 text-center mb-8">
            {{ t('marketing.pricing.subtitle') }}
          </p>

          <div class="flex justify-center mb-10">
            <div
              role="group"
              :aria-label="t('marketing.pricing.title')"
              class="inline-flex items-center gap-1 rounded-xl border border-gray-200 bg-white p-1"
            >
              <button
                type="button"
                :aria-pressed="!annual"
                class="px-4 py-1.5 text-sm font-semibold rounded-lg transition-colors"
                :class="!annual ? 'bg-brand-600 text-white' : 'text-gray-600 hover:text-gray-900'"
                @click="annual = false"
              >
                {{ t('marketing.pricing.toggle.monthly') }}
              </button>
              <button
                type="button"
                :aria-pressed="annual"
                class="px-4 py-1.5 text-sm font-semibold rounded-lg transition-colors inline-flex items-center gap-2"
                :class="annual ? 'bg-brand-600 text-white' : 'text-gray-600 hover:text-gray-900'"
                @click="annual = true"
              >
                {{ t('marketing.pricing.toggle.annual') }}
                <span
                  class="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full"
                  :class="annual ? 'bg-white/20 text-white' : 'bg-accent-100 text-accent-700'"
                >
                  {{ t('marketing.pricing.toggle.save') }}
                </span>
              </button>
            </div>
          </div>

          <ul class="grid grid-cols-1 md:grid-cols-2 gap-6 list-none m-0 p-0" role="list">
            <li
              v-for="plan in pricingPlans"
              :key="plan.name"
              class="rounded-2xl p-8 relative bg-white hover-lift"
              :class="plan.highlight ? 'border-2 border-brand-600' : 'border border-gray-200'"
            >
              <div
                v-if="plan.highlight"
                class="absolute -top-3 left-6 bg-brand-600 text-white text-xs font-bold px-3 py-1 rounded-full"
              >
                {{ plan.highlight }}
              </div>
              <div
                class="text-sm font-semibold uppercase tracking-wide mb-2"
                :class="plan.highlight ? 'text-brand-600' : 'text-gray-500'"
              >
                {{ plan.name }}
              </div>
              <div class="text-4xl font-extrabold text-gray-900 mb-1">
                {{ annual ? plan.priceAnnual : plan.price }}
              </div>
              <div class="text-gray-400 text-sm mb-1">
                {{ annual ? plan.periodAnnual : plan.period }}
              </div>
              <div class="text-xs text-gray-400 mb-6">{{ plan.tag }}</div>
              <ul class="space-y-2.5 mb-8 list-none m-0 p-0" role="list">
                <li
                  v-for="feat in plan.features"
                  :key="feat"
                  class="flex items-center gap-2 text-sm text-gray-700"
                >
                  <CheckIcon class="w-4 h-4 text-accent-500 shrink-0" aria-hidden="true" />
                  {{ feat }}
                </li>
              </ul>
              <a
                href="/app/register"
                class="block text-center px-6 py-3 rounded-xl font-medium transition-colors"
                :class="
                  plan.highlight
                    ? 'bg-brand-600 text-white hover:bg-brand-700'
                    : 'border border-gray-200 text-gray-700 hover:bg-gray-50'
                "
                >{{ plan.cta }}</a
              >
            </li>
          </ul>

          <p class="text-center text-sm text-gray-400 mt-6">
            {{ t('marketing.pricing.note') }}
          </p>
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
              class="inline-block px-8 py-3.5 bg-brand-600 text-white font-semibold rounded-2xl hover:bg-brand-700 transition-colors text-lg"
              >{{ t('marketing.cta.primaryCta') }}</a
            >
            <a
              href="#faq"
              class="inline-block px-8 py-3.5 border border-gray-200 text-gray-700 font-semibold rounded-2xl hover:bg-gray-50 transition-colors text-lg"
              >{{ t('marketing.cta.secondaryCta') }}</a
            >
          </div>
        </div>
      </section>

      <!-- ── FAQ ── -->
      <section id="faq" aria-labelledby="faq-heading" class="bg-gray-50 px-6 py-20 scroll-mt-24">
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
                  class="w-full flex items-center justify-between px-6 py-4 text-left text-sm font-semibold text-gray-900 hover:bg-gray-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-inset"
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
              <dd :id="`faq-panel-${i}`" :aria-labelledby="`faq-btn-${i}`">
                <div
                  v-if="faqOpen === i"
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
    <footer class="border-t border-gray-100 px-6 py-12 pb-28 md:pb-12" role="contentinfo">
      <div class="max-w-6xl mx-auto">
        <div class="grid grid-cols-1 md:grid-cols-5 gap-8 mb-10">
          <div class="md:col-span-1">
            <div class="flex items-center gap-2 mb-2">
              <div
                class="w-6 h-6 rounded-lg bg-brand-600 flex items-center justify-center"
                aria-hidden="true"
              >
                <span class="text-white text-xs font-bold">L</span>
              </div>
              <span class="text-sm font-semibold text-gray-900">
                {{ t('marketing.footer.productName') }}
              </span>
            </div>
            <p class="text-xs text-gray-400 leading-relaxed">
              {{ t('marketing.footer.tagline') }}
            </p>
          </div>

          <nav
            v-for="col in footerColumns"
            :key="col.title"
            :aria-label="col.title"
            class="md:col-span-1"
          >
            <h3 class="text-sm font-semibold text-gray-900 mb-3">{{ col.title }}</h3>
            <ul class="space-y-2 list-none m-0 p-0" role="list">
              <li v-for="link in col.links" :key="link.label">
                <a
                  :href="link.href"
                  class="text-sm text-gray-500 hover:text-gray-900 transition-colors"
                  >{{ link.label }}</a
                >
              </li>
            </ul>
          </nav>
        </div>

        <div
          class="border-t border-gray-100 pt-6 flex flex-col-reverse sm:flex-row items-center justify-between gap-4"
        >
          <p class="text-xs text-gray-400 text-center sm:text-left">
            {{ t('marketing.footer.copyright', { year: new Date().getFullYear() }) }}
          </p>
          <LanguageSwitcher variant="footer" />
        </div>
      </div>
    </footer>

    <!-- ── Sticky mobile CTA bar ── -->
    <div
      class="md:hidden fixed inset-x-0 bottom-0 z-40 bg-white/95 backdrop-blur border-t border-gray-200 px-4 py-3 sticky-cta"
      role="region"
      :aria-label="t('marketing.stickyCta.cta')"
    >
      <a
        href="/app/register"
        class="flex items-center justify-center gap-2 w-full px-6 py-3 bg-brand-600 text-white font-semibold rounded-2xl hover:bg-brand-700 transition-colors"
      >
        {{ t('marketing.stickyCta.cta') }}
        <span class="text-xs font-medium opacity-80">· {{ t('marketing.stickyCta.note') }}</span>
      </a>
    </div>
  </div>
</template>

<style scoped>
.hero-glow {
  position: absolute;
  inset: -10% -20% auto -20%;
  height: 70%;
  background: radial-gradient(
    ellipse at center,
    rgba(37, 72, 150, 0.12) 0%,
    rgba(37, 72, 150, 0.04) 35%,
    rgba(255, 255, 255, 0) 70%
  );
  pointer-events: none;
  filter: blur(30px);
  z-index: 0;
}

.hero-floating {
  transition: transform 0.3s ease;
}

.hover-lift {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.hover-lift:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
}

.sticky-cta {
  padding-bottom: calc(0.75rem + env(safe-area-inset-bottom));
}

@media (prefers-reduced-motion: reduce) {
  .hover-lift,
  .hero-floating {
    transition: none;
  }
  .hover-lift:hover {
    transform: none;
  }
}
</style>
