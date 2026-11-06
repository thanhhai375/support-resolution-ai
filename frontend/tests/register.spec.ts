import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

async function fillRegistration(page: Page) {
  await page.getByLabel('Họ và tên', { exact: true }).fill('Nguyễn Văn An')
  await page.getByLabel('Email', { exact: true }).fill('an@example.com')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Password123')
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill('Password123')
  await page.getByLabel('Tôi đồng ý với Điều khoản sử dụng').check()
}

test('register is public, matches reference layout and links back to login', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  await page.getByRole('link', { name: 'Đăng ký tài khoản' }).click()
  await expect(page).toHaveURL('/register')
  await expect(page.getByRole('heading', { name: 'Tạo tài khoản mới' })).toBeVisible()
  await page.screenshot({ path: 'test-results/register-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/register-mobile.png', fullPage: true })
  await page.getByRole('link', { name: 'Đăng nhập', exact: true }).click()
  await expect(page).toHaveURL('/login')
})

test('mismatched passwords and missing consent do not send a registration request', async ({ page }) => {
  let requests = 0
  await page.route('**/api/auth/register', route => { requests++; return route.fulfill({ status: 201, json: {} }) })
  await page.goto('/register')
  await fillRegistration(page)
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill('Different123')
  await page.getByRole('button', { name: 'Đăng ký tài khoản' }).click()
  await expect(page.getByRole('alert')).toHaveText('Mật khẩu xác nhận không trùng khớp.')
  expect(requests).toBe(0)
  await page.getByLabel('Xác nhận mật khẩu', { exact: true }).fill('Password123')
  await page.getByLabel('Tôi đồng ý với Điều khoản sử dụng').uncheck()
  await page.getByRole('button', { name: 'Đăng ký tài khoản' }).click()
  expect(requests).toBe(0)
  await expect(page).toHaveURL('/register')
})

test('successful registration sends user data and returns to login without a session', async ({ page }) => {
  await page.route('**/api/auth/register', async route => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({ full_name: 'Nguyễn Văn An', email: 'an@example.com', password: 'Password123' })
    await route.fulfill({ status: 201, json: { id: 'new-user' } })
  })
  await page.goto('/register')
  await fillRegistration(page)
  await page.getByRole('button', { name: 'Đăng ký tài khoản' }).click()
  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('status')).toContainText('Đăng ký thành công')
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue('an@example.com')
  expect(await page.evaluate(() => sessionStorage.getItem('access_token') ?? localStorage.getItem('access_token'))).toBeNull()
})

for (const [status, message] of [[409, 'Email này đã được đăng ký.'], [404, 'Máy chủ hiện chưa hỗ trợ đăng ký tài khoản.']] as const) {
  test(`registration API ${status} shows an honest error and preserves form`, async ({ page }) => {
    await page.route('**/api/auth/register', route => route.fulfill({ status, json: {} }))
    await page.goto('/register')
    await fillRegistration(page)
    await page.getByRole('button', { name: 'Đăng ký tài khoản' }).click()
    await expect(page.getByRole('alert')).toContainText(message)
    await expect(page).toHaveURL('/register')
    await expect(page.getByLabel('Email', { exact: true })).toHaveValue('an@example.com')
    await expect(page.getByRole('button', { name: 'Đăng ký tài khoản' })).toBeEnabled()
  })
}
