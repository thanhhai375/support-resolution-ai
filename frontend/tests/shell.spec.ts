import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

function jwt(expiresInSeconds = 3600) {
  const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url')
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: 'admin@supportai.vn', exp: Math.floor(Date.now() / 1000) + expiresInSeconds })}.test-signature`
}

async function session(page: Page, token = jwt()) {
  await page.addInitScript(value => sessionStorage.setItem('access_token', value), token)
}

test.beforeEach(async ({ page }) => {
  // Deliberate API failure exercises the existing mock-ticket fallback.
  await page.route('**/api/tickets', route => route.fulfill({ status: 503, body: '{}' }))
})

for (const path of ['/', '/dashboard', '/tickets?search=TK-1024', '/ai-settings', '/analytics', '/knowledge-base', '/unknown']) {
  test(`unauthenticated ${path} redirects without mounting workspace`, async ({ page }) => {
    let ticketRequests = 0
    page.on('request', request => { if (request.url().endsWith('/api/tickets')) ticketRequests++ })
    await page.goto(path)
    await expect(page).toHaveURL('/login')
    await expect(page.getByRole('heading', { name: 'Đăng nhập vào hệ thống' })).toBeVisible()
    await expect(page.getByRole('navigation')).toHaveCount(0)
    expect(ticketRequests).toBe(0)
  })
}

for (const token of ['broken-token', 'a.b.c', jwt(-60)]) {
  test(`invalid or expired session ${token.slice(0, 12)} redirects`, async ({ page }) => {
    await session(page, token)
    await page.goto('/tickets')
    await expect(page).toHaveURL('/login')
    await expect.poll(() => page.evaluate(() => sessionStorage.getItem('access_token'))).toBeNull()
  })
}

test('login stores JWT, returns to intended route and logout protects history', async ({ page }) => {
  const token = jwt()
  await page.route('**/api/auth/login', async route => {
    expect(route.request().postDataJSON()).toEqual({ email: 'admin@supportai.vn', password: 'secret' })
    await route.fulfill({ json: { access_token: token, token_type: 'bearer' } })
  })
  await page.goto('/tickets?search=TK-1024')
  await page.getByLabel('Email', { exact: true }).fill('admin@supportai.vn')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('secret')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL('/tickets?search=TK-1024')
  await expect(page.getByRole('row')).toHaveCount(2)
  expect(await page.evaluate(() => sessionStorage.getItem('access_token'))).toBe(token)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Danh sách ticket' })).toBeVisible()
  await page.getByRole('link', { name: 'Live Dashboard', exact: true }).click()
  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page).toHaveURL('/login')
  expect(await page.evaluate(() => sessionStorage.getItem('access_token'))).toBeNull()
  await page.goBack()
  await expect(page).toHaveURL('/login')
})

test('failed login displays error and never creates a session', async ({ page }) => {
  await page.route('**/api/auth/login', route => route.fulfill({ status: 401, json: { detail: 'Incorrect email or password' } }))
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill('admin@supportai.vn')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('wrong')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveText('Email hoặc mật khẩu không đúng.')
  await expect(page).toHaveURL('/login')
  expect(await page.evaluate(() => sessionStorage.getItem('access_token'))).toBeNull()
})

test('normal mode rejects demo tokens and hides demo sign-in', async ({ page }) => {
  const token = jwt()
  const parts = token.split('.')
  const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString()) as Record<string, unknown>
  parts[1] = Buffer.from(JSON.stringify({ ...payload, demo: true })).toString('base64url')
  await session(page, parts.join('.'))
  await page.goto('/dashboard')
  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('button', { name: 'Điền tài khoản demo' })).toHaveCount(0)
})

test('navigation uses history without reloading or losing ticket changes', async ({ page }) => {
  await session(page)
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Tổng quan hệ thống' })).toBeVisible()
  await page.evaluate(() => { (window as Window & { documentMarker?: string }).documentMarker = 'same-document' })
  await page.getByRole('link', { name: 'Ticket Feed', exact: true }).click()
  await page.getByRole('button', { name: 'Tạo ticket', exact: false }).first().click()
  await page.getByLabel('Tiêu đề ticket').fill('Ticket giữ nguyên khi chuyển trang')
  await page.getByLabel('Tên khách hàng').fill('Khách hàng thử nghiệm')
  await page.getByRole('button', { name: 'Tạo ticket', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Ticket giữ nguyên khi chuyển trang' })).toBeVisible()
  await page.getByRole('link', { name: 'AI Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'AI Settings' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'AI Settings', exact: true })).toHaveAttribute('aria-current', 'page')
  await page.goBack()
  await expect(page).toHaveURL('/tickets')
  await expect(page.getByRole('button', { name: 'Ticket giữ nguyên khi chuyển trang' })).toBeVisible()
  expect(await page.evaluate(() => (window as Window & { documentMarker?: string }).documentMarker)).toBe('same-document')
})

test('active session expiration redirects automatically', async ({ page }) => {
  await page.clock.install()
  await session(page, jwt(30))
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Tổng quan hệ thống' })).toBeVisible()
  await page.clock.fastForward(31_000)
  await expect(page).toHaveURL('/login')
})

test('localStorage token does not authorize a session', async ({ page }) => {
  await page.addInitScript(token => localStorage.setItem('access_token', token), jwt())
  await page.goto('/knowledge-base')
  await expect(page).toHaveURL('/login')
})

test('knowledge base uses protected layout', async ({ page }) => {
  await session(page)
  await page.goto('/dashboard')
  await page.getByRole('link', { name: 'Knowledge Base', exact: true }).click()
  await expect(page).toHaveURL('/knowledge-base')
  await expect(page.getByRole('heading', { name: 'Thư viện tài liệu' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Knowledge Base' })).toHaveAttribute('aria-current', 'page')
  await page.getByLabel('Tìm tài liệu').fill('biến tần')
  await expect(page.getByRole('heading', { name: 'Không tìm thấy tài liệu' })).toBeVisible()
})

for (const width of [320, 390, 768, 1440]) {
  test(`responsive shell ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await session(page)
    await page.goto('/dashboard')
    await expect(page.getByRole('heading', { name: 'Tổng quan hệ thống' })).toBeVisible()
    if (width <= 720) {
      await expect(page.getByRole('navigation')).not.toBeVisible()
      await page.getByRole('button', { name: 'Mở menu điều hướng' }).click()
      await expect(page.getByRole('dialog', { name: 'Workspace' })).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(page.getByRole('button', { name: 'Mở menu điều hướng' })).toBeFocused()
      await page.getByRole('button', { name: 'Mở menu điều hướng' }).click()
    }
    await page.getByRole('link', { name: 'Ticket Feed', exact: true }).click()
    await expect(page).toHaveURL('/tickets')
    if (width <= 720) await expect(page.getByRole('navigation')).not.toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    expect(await page.evaluate(() => window.scrollY)).toBe(0)
    await page.screenshot({ path: `test-results/shell-${width}.png`, fullPage: true })
  })
}

test('ticket detail supports suggested replies, status updates and persistence', async ({ page }) => {
  await session(page)
  await page.goto('/tickets/TK-1024')
  await expect(page.getByRole('heading', { name: 'Không thể đăng nhập vào tài khoản' })).toBeVisible()
  await page.getByRole('button', { name: 'Dùng gợi ý' }).click()
  await expect(page.getByLabel('Nội dung phản hồi')).not.toBeEmpty()
  await page.getByRole('button', { name: 'Gửi phản hồi' }).click()
  await expect(page.getByLabel('Nội dung phản hồi')).toBeEmpty()
  await expect(page.locator('.agent-message')).toHaveCount(1)
  await page.getByLabel('Trạng thái', { exact: true }).selectOption('PROCESSING')
  await page.reload()
  await expect(page.locator('.agent-message')).toHaveCount(1)
  await expect(page.getByLabel('Trạng thái', { exact: true })).toHaveValue('PROCESSING')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/ticket-detail.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('reference screens render and ticket filters work', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  await page.screenshot({ path: 'test-results/login.png', fullPage: true })
  await page.evaluate(token => sessionStorage.setItem('access_token', token), jwt())
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Tổng quan hệ thống' })).toBeVisible()
  await page.screenshot({ path: 'test-results/dashboard.png', fullPage: true })
  await page.getByRole('link', { name: 'Analytics', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Phân tích hiệu suất hỗ trợ' })).toBeVisible()
  await page.screenshot({ path: 'test-results/analytics.png', fullPage: true })
  await page.getByRole('link', { name: 'Ticket Feed', exact: true }).click()
  await page.getByLabel('Lọc mức ưu tiên').selectOption('URGENT')
  await expect(page.getByRole('row')).toHaveCount(2)
  await expect(page.getByRole('button', { name: 'TK-1022', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'TK-1022', exact: true }).click()
  await expect(page).toHaveURL('/tickets/TK-1022')
})
