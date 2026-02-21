# i18next React Integration

## Overview
- **i18next**: Internationalization framework for JavaScript/TypeScript
- **react-i18next**: React bindings for i18next
- Supports code-splitting, lazy loading, and pluralization

## Version Info (2025)
- **i18next**: v24.x
- **react-i18next**: v15.x

## Installation
```bash
npm install i18next react-i18next i18next-browser-languagedetector

# For backend integration
npm install i18next-http-backend
```

## Basic Setup

### 1. Configuration (i18n.ts)
```typescript
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import Backend from 'i18next-http-backend'

i18n
  .use(Backend) // Load translations from files
  .use(LanguageDetector) // Detect user language
  .use(initReactI18next) // Bind react-i18next
  .init({
    fallbackLng: 'en',
    debug: process.env.NODE_ENV === 'development',
    
    interpolation: {
      escapeValue: false, // React already escapes
    },
    
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },
    
    // Default namespace
    defaultNS: 'common',
    
    // Available namespaces
    ns: ['common', 'validation', 'dashboard'],
  })

export default i18n
```

### 2. Initialize in App (main.tsx)
```tsx
import { I18nextProvider } from 'react-i18next'
import i18n from './i18n'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <I18nextProvider i18n={i18n}>
    <App />
  </I18nextProvider>,
)
```

### 3. Directory Structure
```
public/
└── locales/
    ├── en/
    │   ├── common.json
    │   ├── validation.json
    │   └── dashboard.json
    └── ja/
        ├── common.json
        ├── validation.json
        └── dashboard.json
```

## Usage in Components

### 1. useTranslation Hook
```tsx
import { useTranslation } from 'react-i18next'

function MyComponent() {
  const { t, i18n } = useTranslation('common')
  
  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng)
  }
  
  return (
    <div>
      <h1>{t('welcome')}</h1>
      <button onClick={() => changeLanguage('en')}>English</button>
      <button onClick={() => changeLanguage('ja')}>日本語</button>
    </div>
  )
}
```

### 2. Translation with Interpolation
```json
// common.json
{
  "greeting": "Hello, {{name}}!",
  "message": "You have {{count}} new messages",
  "message_plural": "You have {{count}} new messages"
}
```

```tsx
const { t } = useTranslation()

<p>{t('greeting', { name: 'John' })}</p>
<p>{t('message', { count: 5 })}</p>
```

### 3. Using Multiple Namespaces
```tsx
const { t: tCommon } = useTranslation('common')
const { t: tValidation } = useTranslation('validation')

function Form() {
  return (
    <>
      <h1>{tCommon('save')}</h1>
      <span>{tValidation('required')}</span>
    </>
  )
}
```

## Namespace Organization

### 1. Feature-based Namespaces
```
locales/
├── en/
│   ├── common.json       # Shared strings (buttons, labels)
│   ├── auth.json         # Auth-related strings
│   ├── dashboard.json    # Dashboard feature
│   ├── settings.json     # Settings feature
│   └── validation.json   # Error messages
└── ja/
    └── ...
```

### 2. Hierarchical Keys
```json
// dashboard.json
{
  "title": "Dashboard",
  "menu": {
    "overview": "Overview",
    "analytics": "Analytics"
  },
  "widgets": {
    "chart": {
      "title": "Sales Chart",
      "subtitle": "Last 30 days"
    }
  }
}
```

```tsx
t('dashboard.menu.overview')
t('dashboard.widgets.chart.title')
```

### 3. Type-safe Translation Keys
```typescript
// types/i18n.d.ts
export interface Resources {
  common: {
    welcome: string
    goodbye: string
  }
  dashboard: {
    title: string
    menu: {
      overview: string
      analytics: string
    }
  }
}

declare module 'i18next' {
  interface CustomTypeOptions {
    resources: Resources
  }
}
```

```tsx
// Now you get autocomplete!
const { t } = useTranslation('dashboard')
t('menu.overview') // Fully typed
```

## Code-splitting & Lazy Loading

### 1. Load Namespaces on Demand
```tsx
import { useTranslation } from 'react-i18next'

function Dashboard() {
  const { t, ready } = useTranslation('dashboard', { useSuspense: false })
  
  if (!ready) {
    return <div>Loading translations...</div>
  }
  
  return <h1>{t('title')}</h1>
}
```

### 2. Route-based Loading
```tsx
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

function DashboardPage() {
  const { i18n } = useTranslation()
  
  useEffect(() => {
    // Load dashboard namespace before rendering
    i18n.loadNamespaces('dashboard').then(() => {
      // Translations loaded
    })
  }, [i18n])
  
  // ...
}
```

### 3. Suspense-based Loading
```tsx
import { Suspense } from 'react'
import { useTranslation } from 'react-i18next'

function Dashboard() {
  const { t } = useTranslation('dashboard') // Suspends until loaded
  
  return <h1>{t('title')}</h1>
}

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Dashboard />
    </Suspense>
  )
}
```

## Advanced Patterns

### 1. Pluralization
```json
{
  "item": "One item",
  "item_plural": "{{count}} items",
  "item_with_inclusion": "{{count}} item",
  "item_with_inclusion_plural": "{{count}} items"
}
```

```tsx
t('item', { count: 1 }) // "One item"
t('item', { count: 5 }) // "5 items"
```

### 2. Date/Number Formatting
```tsx
import { format } from 'date-fns'
import { useTranslation } from 'react-i18next'

function DateFormatter({ date }: { date: Date }) {
  const { i18n } = useTranslation()
  
  return (
    <time>
      {format(date, 'PP', { locale: i18n.language === 'ja' ? ja : en })}
    </time>
  )
}
```

### 3. Context-aware Translations
```json
{
  "friend": "A friend",
  "friend_male": "A boyfriend",
  "friend_female": "A girlfriend"
}
```

```tsx
t('friend', { context: 'male' }) // "A boyfriend"
t('friend', { context: 'female' }) // "A girlfriend"
```

### 4. Saving Missing Keys
```typescript
i18n.use(Backend).init({
  backend: {
    loadPath: '/locales/{{lng}}/{{ns}}.json',
    addPath: '/locales/{{lng}}/{{ns}}.json', // Save missing keys
  },
  saveMissing: true,
  saveMissingTo: 'current',
})
```

## React Server Components (Next.js)

```tsx
// app/[locale]/layout.tsx
import { NextIntlClientProvider } from 'next-intl'
import { getMessages } from 'next-intl/server'

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode
  params: { locale: string }
}) {
  const messages = await getMessages()
  
  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
```

## Best Practices

1. **Use feature-based namespaces**: Organize by feature, not by type
2. **Lazy load namespaces**: Load translations only when needed
3. **Use interpolation**: For dynamic values (names, counts)
4. **Keep keys simple**: Avoid long, nested keys
5. **Use type-safe keys**: Generate types from JSON files
6. **Handle missing keys**: Implement fallback strategy
7. **Test all languages**: Check layout for different languages

## Common Pitfalls

### 1. Missing Namespaces
```tsx
// ❌ Will throw if namespace not loaded
const { t } = useTranslation('dashboard')

// ✅ Check if ready
const { t, ready } = useTranslation('dashboard', { useSuspense: false })
if (!ready) return <div>Loading...</div>
```

### 2. Hardcoded Strings
```tsx
// ❌ Hardcoded
<button>Submit</button>

// ✅ Translated
<button>{t('common.submit')}</button>
```

### 3. Complex Nested Keys
```json
// ❌ Too nested
{"dashboard": {"menu": {"items": {"overview": {"title": "Overview"}}}}}

// ✅ Flat structure
{"dashboard": {"menuOverviewTitle": "Overview"}}
```

## Official Resources
- [i18next Documentation](https://www.i18next.com/)
- [react-i18next Documentation](https://react.i18next.com/)
- [TypeScript Guide](https://www.i18next.com/overview/typescript)
