export function calculationOrderingOptions(paymentField = 'monthlyPayment') {
  return [
    ['createdAt', 'Дата'], ['city', 'Город'], ['realEstateComplex', 'Объект'],
    ['finalPropertyCost', 'Стоимость'], ['initialPaymentRubles', 'Первый взнос'],
    [paymentField, 'Платёж'], ['mortgageTermMonths', 'Срок'], ['annualRate', 'Ставка'],
  ].flatMap(([value, label]) => [
    { value, label: `${label}: по возрастанию` },
    { value: `-${value}`, label: `${label}: по убыванию` },
  ])
}
