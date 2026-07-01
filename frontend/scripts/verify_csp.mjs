#!/usr/bin/env node
/**
 * Smoke-test production CSP against a local dist server (scripts/csp_preview_server.py).
 * Run: npm run build && node scripts/verify_csp.mjs
 */
import { chromium } from 'playwright'

const BASE_URL = process.env.CSP_PREVIEW_URL ?? 'http://127.0.0.1:4173'

const SAMPLE_REPORT = {
  trades: [{ symbol: 'AAPL', date: '2024-01-15', action: 'BUY', shares: 10, price: 150 }],
  pnl: {
    trade_pnl: [{ symbol: 'AAPL', pnl: 50 }],
    total_pnl: 50,
    total_return_pct: 10,
    avg_holding_days_winners: 5,
    avg_holding_days_losers: null,
    equity_curve: [
      { date: '2024-01-15', cumulative_pnl: 0 },
      { date: '2024-02-15', cumulative_pnl: 50 },
    ],
  },
  spy_benchmark: { total_return_pct: 5, start_date: '2024-01-15', end_date: '2024-02-15' },
  qqq_benchmark: { total_return_pct: 8 },
  warnings: [],
  notices: [],
}

async function main() {
  const violations = []
  const consoleErrors = []

  const browser = await chromium.launch()
  const page = await browser.newPage()

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => consoleErrors.push(String(err)))

  await page.addInitScript(() => {
    window.__cspViolations = []
    document.addEventListener('securitypolicyviolation', (e) => {
      window.__cspViolations.push({
        violatedDirective: e.violatedDirective,
        effectiveDirective: e.effectiveDirective,
        blockedURI: e.blockedURI,
      })
    })
  })

  await page.goto(BASE_URL, { waitUntil: 'networkidle' })

  await page.evaluate((report) => {
    sessionStorage.setItem('tradeReport', JSON.stringify(report))
  }, SAMPLE_REPORT)

  await page.goto(`${BASE_URL}/report`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)

  const pageViolations = await page.evaluate(() => window.__cspViolations ?? [])
  violations.push(...pageViolations)

  const hasReport = await page.getByText('Your Trade Analysis').isVisible().catch(() => false)
  const hasBenchmark = await page.getByText('Return Comparison').isVisible().catch(() => false)
  const hasEquity = await page.getByText('P&L Over Time').isVisible().catch(() => false)

  await browser.close()

  const cspErrors = consoleErrors.filter((line) =>
    /content security policy|csp|refused to apply inline style|refused to execute/i.test(line)
  )

  if (!hasReport) {
    console.error('FAIL: report page did not render')
    process.exit(1)
  }

  if (violations.length > 0 || cspErrors.length > 0) {
    console.error('FAIL: CSP violations detected')
    console.error(JSON.stringify({ violations, cspErrors }, null, 2))
    process.exit(1)
  }

  console.log('PASS: CSP smoke test')
  console.log(JSON.stringify({ hasReport, hasBenchmark, hasEquity }, null, 2))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
