targetScope = 'subscription'

@description('Name of the budget resource.')
param budgetName string

@description('Monthly budget amount in the subscription currency.')
param amount int

@description('Budget start date. Must be the first day of a month in YYYY-MM-DD format.')
param startDate string

@description('Budget end date in YYYY-MM-DD format.')
param endDate string

@description('Email recipients for budget notifications.')
param contactEmails array

@description('Optional action group resource IDs for budget notifications.')
param contactGroupIds array = []

@description('Locale for budget email notifications.')
@allowed([
  'en-us'
  'ja-jp'
])
param locale string = 'ja-jp'

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: budgetName
  properties: {
    amount: amount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
      endDate: endDate
    }
    notifications: {
      Actual50Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: contactEmails
        contactGroups: contactGroupIds
        locale: locale
      }
      Actual80Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: contactEmails
        contactGroups: contactGroupIds
        locale: locale
      }
      Actual100Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: contactEmails
        contactGroups: contactGroupIds
        locale: locale
      }
    }
  }
}

output budgetResourceId string = budget.id
