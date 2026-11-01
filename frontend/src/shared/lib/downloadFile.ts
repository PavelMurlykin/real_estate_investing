import type { DownloadedFile } from '@/api/client'

export function downloadFile({ blob, filename }: DownloadedFile) {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
