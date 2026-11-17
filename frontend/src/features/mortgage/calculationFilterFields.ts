export const calculationRanges = [
  ['cost', 'Стоимость, ₽'], ['initialPayment', 'Первый взнос, ₽'],
  ['monthlyPayment', 'Последний / основной платёж, ₽'],
  ['term', 'Срок, лет'], ['rate', 'Ставка, %'],
] as const

export const calculationFilterNames = [
  'city', 'regionLocationId', 'districtLocationId', 'localityId', 'locationId',
  ...calculationRanges.flatMap(([name]) => [`${name}From`, `${name}To`]),
]
