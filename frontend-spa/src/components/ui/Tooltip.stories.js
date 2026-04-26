import Tooltip from './Tooltip.vue';
const meta = {
    component: Tooltip,
    tags: ['autodocs'],
    argTypes: {
        placement: { control: 'select', options: ['top', 'bottom', 'left', 'right'] },
    },
};
export default meta;
export const Top = {
    render: (args) => ({
        components: { Tooltip },
        setup: () => ({ args }),
        template: `
      <div class="flex items-center justify-center h-32">
        <Tooltip v-bind="args">
          <button class="px-3 py-2 bg-gray-100 rounded-lg text-sm">Hover me</button>
        </Tooltip>
      </div>
    `,
    }),
    args: { content: 'This is a tooltip', placement: 'top' },
};
export const Bottom = {
    render: (args) => ({
        components: { Tooltip },
        setup: () => ({ args }),
        template: `
      <div class="flex items-center justify-center h-32">
        <Tooltip v-bind="args">
          <button class="px-3 py-2 bg-gray-100 rounded-lg text-sm">Hover me</button>
        </Tooltip>
      </div>
    `,
    }),
    args: { content: 'Tooltip below', placement: 'bottom' },
};
export const Right = {
    render: (args) => ({
        components: { Tooltip },
        setup: () => ({ args }),
        template: `
      <div class="flex items-center justify-center h-32">
        <Tooltip v-bind="args">
          <button class="px-3 py-2 bg-gray-100 rounded-lg text-sm">Hover me</button>
        </Tooltip>
      </div>
    `,
    }),
    args: { content: 'Tooltip right', placement: 'right' },
};
