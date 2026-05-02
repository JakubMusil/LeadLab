<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import { DocumentIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

const toast = useToast()
const firmStore = useFirmStore()

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TemplItem {
  id?: string
  description: string
  quantity: number
  unit_price: number
  discount: number
  vat_rate: number
  position: number
}

interface ProposalTemplate {
  id: string
  name: string
  intro_text: string
  closing_text: string
  items: TemplItem[]
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const propTemplates = ref<ProposalTemplate[]>([])
const propTemplatesLoading = ref(false)
const newTemplateName = ref('')
const newTemplateIntro = ref('')
const newTemplateClosing = ref('')
const newTemplateCreating = ref(false)
const expandedTemplate = ref<string | null>(null)
const newTmplItemDesc = ref('')
const newTmplItemQty = ref(1)
const newTmplItemPrice = ref(0)
const addingTmplItem = ref(false)
const confirmDeleteTemplateId = ref<string | null>(null)

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function loadPropTemplates() {
  propTemplatesLoading.value = true
  const res = await api.get<ProposalTemplate[]>('/api/v1/crm/proposal-templates')
  propTemplatesLoading.value = false
  if (res.ok && Array.isArray(res.data)) propTemplates.value = res.data
}

async function createPropTemplate() {
  if (!newTemplateName.value.trim()) return
  newTemplateCreating.value = true
  const res = await api.post<ProposalTemplate>('/api/v1/crm/proposal-templates', {
    name: newTemplateName.value.trim(),
    intro_text: newTemplateIntro.value,
    closing_text: newTemplateClosing.value,
  })
  newTemplateCreating.value = false
  if (res.ok && res.data) {
    propTemplates.value.unshift(res.data)
    newTemplateName.value = ''
    newTemplateIntro.value = ''
    newTemplateClosing.value = ''
    toast.success('Template created.')
  } else {
    toast.error('Failed to create template.')
  }
}

async function deletePropTemplate(id: string) {
  const res = await api.delete(`/api/v1/crm/proposal-templates/${id}`)
  if (res.ok || res.status === 204) {
    propTemplates.value = propTemplates.value.filter((t) => t.id !== id)
    if (expandedTemplate.value === id) expandedTemplate.value = null
    toast.success('Template deleted.')
  } else {
    toast.error('Failed to delete template.')
  }
}

async function addTmplItem(template: ProposalTemplate) {
  if (!newTmplItemDesc.value.trim()) return
  addingTmplItem.value = true
  const res = await api.post<TemplItem>(`/api/v1/crm/proposal-templates/${template.id}/items`, {
    description: newTmplItemDesc.value.trim(),
    quantity: newTmplItemQty.value,
    unit_price: newTmplItemPrice.value,
    discount: 0,
    vat_rate: 0,
    position: template.items.length,
  })
  addingTmplItem.value = false
  if (res.ok) {
    template.items.push(res.data)
    newTmplItemDesc.value = ''
    newTmplItemQty.value = 1
    newTmplItemPrice.value = 0
  } else {
    toast.error('Failed to add item.')
  }
}

async function deleteTmplItem(template: ProposalTemplate, itemId: string) {
  const res = await api.delete(`/api/v1/crm/proposal-templates/${template.id}/items/${itemId}`)
  if (res.ok || res.status === 204) {
    template.items = template.items.filter((i) => i.id !== itemId)
  } else {
    toast.error('Failed to delete item.')
  }
}

onMounted(() => {
  firmStore.fetchFirms().then(() => {
    if (firmStore.activeFirm) {
      loadPropTemplates()
    }
  })
})
</script>

<template>
  <div class="p-6 space-y-5">
    <!-- Header -->
    <div>
      <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">Proposal Templates</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
        Create reusable proposal templates with pre-filled items, intro text, and closing text.
      </p>
    </div>

    <!-- Loading -->
    <div v-if="propTemplatesLoading" class="animate-pulse space-y-2">
      <div v-for="i in 3" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty -->
    <div v-else-if="propTemplates.length === 0" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-10 text-center">
      <DocumentIcon class="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">No proposal templates yet</p>
      <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Create your first template below to speed up proposal creation.</p>
    </div>

    <!-- Template list -->
    <div v-else class="space-y-3">
      <div
        v-for="tmpl in propTemplates"
        :key="tmpl.id"
        class="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl overflow-hidden"
      >
        <div class="flex items-center gap-3 px-5 py-4">
          <div class="w-9 h-9 rounded-xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center flex-shrink-0">
            <span class="text-lg">📝</span>
          </div>
          <button
            class="flex-1 text-left"
            @click="expandedTemplate = expandedTemplate === tmpl.id ? null : tmpl.id"
          >
            <span class="text-sm font-semibold text-gray-800 dark:text-gray-100">{{ tmpl.name }}</span>
            <span class="text-xs text-gray-400 dark:text-gray-500 ml-2">({{ tmpl.items.length }} items)</span>
          </button>
          <button
            class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1"
            @click="expandedTemplate = expandedTemplate === tmpl.id ? null : tmpl.id"
          >{{ expandedTemplate === tmpl.id ? '▲ Close' : '▼ Expand' }}</button>
          <button
            class="text-xs text-red-400 hover:text-red-600 border border-red-200 dark:border-red-800 rounded-lg px-2 py-1"
            @click="confirmDeleteTemplateId = tmpl.id"
          >Delete</button>
        </div>

        <!-- Expanded template details -->
        <div v-if="expandedTemplate === tmpl.id" class="border-t border-gray-100 dark:border-gray-700 px-5 pb-4">
          <!-- Intro / closing text (read-only display) -->
          <div v-if="tmpl.intro_text || tmpl.closing_text" class="grid grid-cols-2 gap-4 py-3 text-xs text-gray-500 dark:text-gray-400 border-b border-gray-50 dark:border-gray-700 mb-3">
            <div v-if="tmpl.intro_text">
              <span class="font-medium text-gray-600 dark:text-gray-300 block mb-1">Intro text</span>
              <p class="whitespace-pre-wrap line-clamp-3">{{ tmpl.intro_text }}</p>
            </div>
            <div v-if="tmpl.closing_text">
              <span class="font-medium text-gray-600 dark:text-gray-300 block mb-1">Closing text</span>
              <p class="whitespace-pre-wrap line-clamp-3">{{ tmpl.closing_text }}</p>
            </div>
          </div>

          <!-- Items table -->
          <div v-if="tmpl.items.length === 0" class="text-xs text-gray-400 dark:text-gray-500 py-3">No items in this template.</div>
          <table v-else class="w-full text-xs mb-3 mt-2">
            <thead>
              <tr class="border-b border-gray-100 dark:border-gray-700 text-gray-500 dark:text-gray-400">
                <th class="text-left pb-2">Description</th>
                <th class="text-right pb-2 w-14">Qty</th>
                <th class="text-right pb-2 w-20">Unit price</th>
                <th class="w-8"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50 dark:divide-gray-700/50">
              <tr v-for="item in tmpl.items" :key="item.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <td class="py-2 text-gray-700 dark:text-gray-300">{{ item.description }}</td>
                <td class="py-2 text-right text-gray-500 dark:text-gray-400">{{ item.quantity }}</td>
                <td class="py-2 text-right text-gray-500 dark:text-gray-400">{{ Number(item.unit_price).toFixed(2) }}</td>
                <td class="py-2 text-right">
                  <button
                    class="text-gray-300 hover:text-red-500 transition-colors"
                    :aria-label="`Delete item ${item.description}`"
                    @click="deleteTmplItem(tmpl, item.id!)"><XMarkIcon class="w-4 h-4" /></button>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Add item to template -->
          <div class="flex flex-wrap gap-2 bg-gray-50 dark:bg-gray-700/30 rounded-xl p-3">
            <input v-model="newTmplItemDesc" type="text" placeholder="Item description" class="flex-1 min-w-36 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2.5 py-1.5 text-xs focus:outline-none focus:border-red-400" />
            <input v-model.number="newTmplItemQty" type="number" min="1" step="1" placeholder="Qty" class="w-16 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs text-right focus:outline-none focus:border-red-400" />
            <input v-model.number="newTmplItemPrice" type="number" min="0" step="0.01" placeholder="Price" class="w-24 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs text-right focus:outline-none focus:border-red-400" />
            <button
              :disabled="addingTmplItem || !newTmplItemDesc.trim()"
              class="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
              @click="addTmplItem(tmpl)"
            >+ Add item</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create new template card -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-dashed border-gray-200 dark:border-gray-600 p-5 space-y-3">
      <h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300">New Template</h2>
      <input
        v-model="newTemplateName"
        type="text"
        placeholder="Template name *"
        class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
      />
      <textarea
        v-model="newTemplateIntro"
        rows="2"
        placeholder="Intro text (optional)…"
        class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
      />
      <textarea
        v-model="newTemplateClosing"
        rows="2"
        placeholder="Closing text (optional)…"
        class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
      />
      <button
        :disabled="newTemplateCreating || !newTemplateName.trim()"
        class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
        @click="createPropTemplate"
      >{{ newTemplateCreating ? 'Creating…' : '+ Create Template' }}</button>
    </div>
  </div>

  <ConfirmDeleteModal
    :open="!!confirmDeleteTemplateId"
    @confirm="() => { const id = confirmDeleteTemplateId; confirmDeleteTemplateId = null; if (id) deletePropTemplate(id) }"
    @cancel="confirmDeleteTemplateId = null"
  />
</template>
