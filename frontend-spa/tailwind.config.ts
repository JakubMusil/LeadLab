import type { Config } from 'tailwindcss'
import typography from '@tailwindcss/typography'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      // Customize the @tailwindcss/typography `prose` palette so rich-text
      // content rendered via <RichTextDisplay> and inside the Tiptap editor
      // has WCAG-AA compliant contrast in light mode (the previous setup
      // relied on missing prose styles and inherited colors from light
      // containers like text-gray-500, which caused poor contrast).
      typography: () => ({
        DEFAULT: {
          css: {
            // Body text — gray-800 on white = ~13:1 contrast
            '--tw-prose-body': '#1f2937',
            '--tw-prose-headings': '#111827',
            '--tw-prose-lead': '#374151',
            '--tw-prose-links': '#2563eb',
            '--tw-prose-bold': '#111827',
            '--tw-prose-counters': '#374151',
            '--tw-prose-bullets': '#6b7280',
            '--tw-prose-hr': '#d1d5db',
            '--tw-prose-quotes': '#111827',
            '--tw-prose-quote-borders': '#d1d5db',
            '--tw-prose-captions': '#374151',
            '--tw-prose-code': '#111827',
            '--tw-prose-pre-code': '#e5e7eb',
            '--tw-prose-pre-bg': '#1f2937',
            '--tw-prose-th-borders': '#9ca3af',
            '--tw-prose-td-borders': '#d1d5db',
            // Dark-mode invert palette (used via .dark .prose-invert)
            '--tw-prose-invert-body': '#e5e7eb',
            '--tw-prose-invert-headings': '#f9fafb',
            '--tw-prose-invert-lead': '#d1d5db',
            '--tw-prose-invert-links': '#60a5fa',
            '--tw-prose-invert-bold': '#f9fafb',
            '--tw-prose-invert-counters': '#d1d5db',
            '--tw-prose-invert-bullets': '#9ca3af',
            '--tw-prose-invert-hr': '#374151',
            '--tw-prose-invert-quotes': '#f3f4f6',
            '--tw-prose-invert-quote-borders': '#374151',
            '--tw-prose-invert-captions': '#d1d5db',
            '--tw-prose-invert-code': '#f9fafb',
            '--tw-prose-invert-pre-code': '#e5e7eb',
            '--tw-prose-invert-pre-bg': '#111827',
            '--tw-prose-invert-th-borders': '#6b7280',
            '--tw-prose-invert-td-borders': '#374151',
          },
        },
      }),
      colors: {
        brand: {
          DEFAULT: '#dc2626',
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
        },
      },
      fontSize: {
        display: ['3rem', { lineHeight: '1.2' }],
        h1: ['2rem', { lineHeight: '1.2' }],
        h2: ['1.5rem', { lineHeight: '1.375' }],
        h3: ['1.25rem', { lineHeight: '1.375' }],
        h4: ['1rem', { lineHeight: '1.5' }],
        body: ['0.875rem', { lineHeight: '1.5' }],
        caption: ['0.75rem', { lineHeight: '1.5' }],
        label: ['0.6875rem', { lineHeight: '1.5' }],
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        xl: '16px',
        '2xl': '20px',
        full: '9999px',
      },
      boxShadow: {
        sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
        xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
      },
    },
  },
  plugins: [typography],
} satisfies Config
