<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
import Modal from './Modal.vue'
import Button from './Button.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    message?: string
    loading?: boolean
  }>(),
  {
    title: undefined,
    message: undefined,
    loading: false,
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const { t } = useI18n()
</script>

<template>
  <Modal
    :open="open"
    :title="title ?? t('deleteModal.title')"
    size="sm"
    @close="emit('cancel')"
  >
    <p class="text-sm text-gray-500 dark:text-gray-400">
      {{ message ?? t('deleteModal.message') }}
    </p>

    <template #footer>
      <Button
        variant="secondary"
        :disabled="loading"
        @click="emit('cancel')"
      >
        {{ t('deleteModal.cancel') }}
      </Button>
      <Button
        variant="primary"
        :loading="loading"
        @click="emit('confirm')"
      >
        {{ t('deleteModal.confirm') }}
      </Button>
    </template>
  </Modal>
</template>
