import { ref } from 'vue';
import Modal from './Modal.vue';
import Button from './Button.vue';
const meta = {
    component: Modal,
    tags: ['autodocs'],
};
export default meta;
export const Default = {
    render: () => ({
        components: { Modal, Button },
        setup() {
            const open = ref(false);
            return { open };
        },
        template: `
      <div>
        <Button @click="open = true">Open Modal</Button>
        <Modal :open="open" title="Example Modal" @close="open = false">
          <p class="text-sm text-gray-600 dark:text-gray-400">
            This is the modal body. Place any content here.
          </p>
          <template #footer>
            <Button variant="secondary" @click="open = false">Cancel</Button>
            <Button @click="open = false">Confirm</Button>
          </template>
        </Modal>
      </div>
    `,
    }),
};
export const Large = {
    render: () => ({
        components: { Modal, Button },
        setup() {
            const open = ref(false);
            return { open };
        },
        template: `
      <div>
        <Button @click="open = true">Open Large Modal</Button>
        <Modal :open="open" title="Large Modal" size="lg" @close="open = false">
          <p class="text-sm text-gray-600 dark:text-gray-400">Large modal content area.</p>
          <template #footer>
            <Button variant="secondary" @click="open = false">Close</Button>
          </template>
        </Modal>
      </div>
    `,
    }),
};
