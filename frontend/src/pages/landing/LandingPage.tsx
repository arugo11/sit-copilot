/**
 * Landing Page
 * Based on docs/frontend.md Section 8.1
 */

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useUiLanguagePreference } from '@/hooks/useUiLanguagePreference'

export function LandingPage() {
  const { t } = useTranslation()
  const { language, setLanguage, isPersisting } = useUiLanguagePreference()

  const onboardingSteps = [
    {
      id: 1,
      title: t('landing.steps.selectLanguage.title'),
      description: t('landing.steps.selectLanguage.description'),
    },
    {
      id: 2,
      title: t('landing.steps.startLecture.title'),
      description: t('landing.steps.startLecture.description'),
    },
    {
      id: 3,
      title: t('landing.steps.askQuestion.title'),
      description: t('landing.steps.askQuestion.description'),
    },
  ]

  return (
    <div className="min-h-screen bg-bg-page">
      <div className="container mx-auto px-4 py-12">
        <div className="grid gap-10 lg:grid-cols-5 lg:items-center lg:gap-12">
          {/* Left Content (60%) */}
          <div className="lg:col-span-3 space-y-8">
            <h1 className="text-3xl font-bold text-fg-primary sm:text-4xl md:text-5xl">
              {t('landing.title')}
            </h1>
            <p className="text-base text-fg-secondary sm:text-lg">
              {t('landing.subtitle')}
            </p>

            {/* Target Audience */}
            <div className="flex flex-wrap gap-4 py-4">
              <div className="badge badge-default">{t('landing.audience.international')}</div>
              <div className="badge badge-default">{t('landing.audience.disability')}</div>
              <div className="badge badge-default">{t('landing.audience.native')}</div>
            </div>

            {/* Onboarding Steps */}
            <div className="space-y-3">
              <h2 className="text-xl font-semibold text-fg-primary">
                {t('landing.steps.title')}
              </h2>
              <ol className="space-y-3">
                {onboardingSteps.map((step) => (
                  <li key={step.id} className="card p-4 flex gap-3 items-start">
                    <span className="badge min-w-7 justify-center bg-accent text-fg-inverse">
                      {step.id}
                    </span>
                    <div>
                      <p className="font-medium text-fg-primary">{step.title}</p>
                      <p className="text-sm text-fg-secondary">{step.description}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            {/* Key Features */}
            <div className="space-y-3">
              <h2 className="text-xl font-semibold text-fg-primary">{t('landing.features.title')}</h2>
              <ul className="space-y-2 text-fg-secondary" role="list">
                <li className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-success mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{t('landing.features.captions')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-success mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{t('landing.features.materials')}</span>
                </li>
                <li className="flex items-start gap-2">
                  <svg className="w-5 h-5 text-success mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{t('landing.features.qa')}</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Right Content (40%) */}
          <div className="space-y-6 lg:col-span-2">
            <div className="card p-6 space-y-4">
              <h2 className="text-xl font-semibold text-fg-primary text-center">
                {t('landing.quickStart.title')}
              </h2>

              {/* Language Selector */}
              <div className="space-y-2">
                <label htmlFor="language" className="block text-sm font-medium text-fg-primary mb-2">
                  {t('landing.languageSelector.label')}
                </label>
                <select
                  id="language"
                  className="input"
                  value={language}
                  onChange={(event) => {
                    const next = event.target.value === 'en' ? 'en' : 'ja'
                    void setLanguage(next)
                  }}
                >
                  <option value="ja">{t('landing.languageSelector.options.ja')}</option>
                  <option value="en">{t('landing.languageSelector.options.en')}</option>
                </select>
                <p className="text-xs text-fg-secondary">
                  {isPersisting
                    ? t('landing.languageSelector.saving')
                    : t('landing.languageSelector.help')}
                </p>
              </div>

              {/* Lecture Start Button */}
              <Link to="/lectures" className="btn btn-primary w-full text-center block">
                {t('landing.demo')}
              </Link>

              <p className="text-xs text-fg-secondary text-center">
                {t('landing.quickStart.note')}
              </p>
            </div>

            <div className="card border-border bg-gradient-to-br from-bg-muted to-bg-surface p-5">
              <h3 className="text-base font-semibold text-fg-primary mb-2">
                {t('landing.support.title')}
              </h3>
              <p className="text-sm text-fg-secondary">
                {t('landing.support.description')}
              </p>
              <div className="mt-3 text-sm text-fg-secondary">
                {t('landing.support.languages')}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
