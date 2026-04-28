/**
 * Shared Document types used across DocumentsView, RealizationDetailView,
 * ManagementDetailView, and any other view that embeds a Documents panel.
 */

export interface DocumentOut {
  id: string
  firm_id?: string
  name: string
  content_type: string
  size_bytes: number
  lead_id?: string | null
  lead_title?: string | null
  customer_id?: string | null
  customer_name?: string | null
  realization_id?: string | null
  realization_title?: string | null
  management_id?: string | null
  management_title?: string | null
  task_id?: string | null
  task_title?: string | null
  proposal_id?: string | null
  proposal_title?: string | null
  uploaded_by_id?: string | null
  uploaded_by_name: string | null
  file_url: string
  created_at: string
}

/**
 * Returns an emoji icon that represents the given MIME type.
 */
export function docFileIcon(contentType: string): string {
  if (contentType.startsWith('image/')) return '🖼️'
  if (contentType === 'application/pdf') return '📄'
  if (contentType.includes('word') || contentType.includes('document')) return '📝'
  if (contentType.includes('excel') || contentType.includes('spreadsheet')) return '📊'
  if (contentType.includes('powerpoint') || contentType.includes('presentation')) return '📋'
  if (contentType.includes('zip') || contentType.includes('archive')) return '🗜️'
  return '📎'
}

/**
 * Returns a Tailwind text-color class that matches the file type icon colour
 * used in the full DocumentsView table.
 */
export function docFileIconColor(contentType: string): string {
  if (contentType.startsWith('image/')) return 'text-purple-500'
  if (contentType === 'application/pdf') return 'text-red-500'
  if (contentType.includes('word') || contentType.includes('document')) return 'text-blue-600'
  if (contentType.includes('excel') || contentType.includes('spreadsheet')) return 'text-green-600'
  if (contentType.includes('powerpoint') || contentType.includes('presentation')) return 'text-orange-500'
  if (contentType.includes('zip') || contentType.includes('archive')) return 'text-yellow-600'
  return 'text-gray-500'
}

/**
 * Format a byte count into a human-readable string (e.g. "1.2 MB").
 */
export function fmtDocBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}
