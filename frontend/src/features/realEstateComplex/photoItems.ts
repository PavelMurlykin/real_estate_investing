import type { RealEstateComplexDetail } from '@/api/schemas'

export function complexPhotoItems(complex?: RealEstateComplexDetail) {
  const photos: { id: number | null; url: string; isPrimary: boolean }[] = []
  if (complex?.photoUrl) {
    const primary = complex.photos?.find((photo) => photo.url === complex.photoUrl)
    photos.push({ id: primary?.id ?? null, url: complex.photoUrl, isPrimary: true })
  }
  for (const photo of complex?.photos ?? []) {
    if (!photos.some((existing) => existing.url === photo.url)) photos.push(photo)
  }
  return photos
}

