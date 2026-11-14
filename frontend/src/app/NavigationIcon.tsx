const paths = {
  home: 'M3 11 12 3l9 8M5 10v11h14V10M9 21v-7h6v7',
  property: 'M4 21V3h11v18M15 9h5v12M8 7h3m-3 4h3m-3 4h3M2 21h20',
  company: 'M3 21V9h8v12M11 21V3h10v18M6 13h2m-2 4h2m7-10h2m-2 4h2m-2 4h2',
  developer: 'M4 16V9l8-5 8 5v7M2 16h20M6 16v5h12v-5M12 4v8',
  complex: 'M2 21h20M4 21V7h7v14M11 21V3h9v18M7 11h1m-1 4h1m7-8h2m-2 4h2m-2 4h2',
  dictionary: 'M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4V4Zm9 3a3 3 0 0 1 3-3h5v15h-4a4 4 0 0 0-4 2',
  location: 'M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0ZM9 10a3 3 0 1 0 6 0 3 3 0 0 0-6 0',
  bank: 'm3 8 9-5 9 5H3Zm1 13h16M6 11v7m6-7v7m6-7v7',
  program: 'M5 3h10l4 4v14H5V3Zm10 0v5h4M8 12h8m-8 4h5',
  offer: 'M3 4h9l9 9-8 8-10-10V4Zm4 4h.01M10 15l5-5',
  rate: 'm6 19 12-14M5 7a2 2 0 1 0 4 0 2 2 0 0 0-4 0Zm10 10a2 2 0 1 0 4 0 2 2 0 0 0-4 0',
  calculator: 'M5 3h14v18H5V3Zm3 4h8M8 12h1m5 0h1m-7 4h1m5 0h1',
  trench: 'm3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4',
  customer: 'M8 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0ZM4 21v-2a8 8 0 0 1 16 0v2',
  addCustomer: 'M5 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0ZM2 21v-2a7 7 0 0 1 11-6M18 14v8m-4-4h8',
  history: 'M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2',
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'm6 6 12 12M18 6 6 18',
} as const

export type NavigationIconName = keyof typeof paths

export function NavigationIcon({ name }: { name: NavigationIconName }) {
  return <svg className="navigation-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
