/// <reference types="vite/client" />

// Ambient module declaration for frappe-gantt — the package ships only an
// ES module (frappe-gantt.es.js) without bundled .d.ts types.  We use it
// via dynamic import + `as any` cast in GanttView.vue, so a minimal `any`
// declaration is sufficient to silence TS7016.
declare module 'frappe-gantt'
