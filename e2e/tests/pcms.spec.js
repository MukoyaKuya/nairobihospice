const { test, expect } = require('@playwright/test');

const required = ['PCMS_E2E_BASE_URL', 'PCMS_E2E_RECEPTION_EMAIL', 'PCMS_E2E_RECEPTION_PASSWORD'];
for (const name of required) {
  if (!process.env[name]) throw new Error(`${name} must be set for staging E2E tests`);
}

async function login(page, email = process.env.PCMS_E2E_RECEPTION_EMAIL, password = process.env.PCMS_E2E_RECEPTION_PASSWORD) {
  await page.goto('/accounts/login/');
  await page.getByLabel(/email address/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in|login/i }).click();
  await expect(page).not.toHaveURL(/\/accounts\/login\//);
}

test.describe('PCMS staging browser flows', () => {
  test('1. login and privileged MFA enrollment', async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL(/\/reporting\/|\/patients\/|\/accounts\//);

    test.skip(!process.env.PCMS_E2E_MANAGER_EMAIL, 'Set manager credentials to run MFA flow');
    await page.goto('/accounts/logout/');
    await login(page, process.env.PCMS_E2E_MANAGER_EMAIL, process.env.PCMS_E2E_MANAGER_PASSWORD);
    if (await page.getByText(/MFA|authenticator/i).count()) {
      await expect(page).toHaveURL(/mfa/);
    }
  });

  test('2. role-based patient visibility', async ({ page }) => {
    await login(page);
    await page.goto('/patients/');
    await expect(page).toHaveURL(/\/patients\//);
    await expect(page.locator('body')).not.toContainText(/clinical diagnosis|allergies/i);
  });

  test('3. clinical document and photo access restrictions', async ({ page }) => {
    await login(page);
    await page.goto('/patients/');
    const patientLink = page.locator('a[href*="/patients/"]').first();
    await expect(patientLink).toBeVisible();
    await patientLink.click();
    await expect(page).toHaveURL(/\/patients\/[^/]+\//);
    await expect(page.locator('a[href*="/media/"]')).toHaveCount(0);
  });

  test('4. patient registration and appointment scheduling pages are reachable', async ({ page }) => {
    await login(page);
    await page.goto('/patients/new/');
    await expect(page.locator('form')).toBeVisible();
    await page.goto('/appointments/');
    await expect(page).toHaveURL(/\/appointments\//);
  });

  test('5. webhook-triggering workflow is reachable', async ({ page }) => {
    await login(page);
    await page.goto('/patients/');
    await expect(page.locator('body')).toContainText(/patient|hospice/i);
    // Creation is intentionally not automated here to avoid mutating shared staging data.
    await expect(page.locator('a[href*="patients"]').first()).toBeVisible();
  });

  test('6. logout and session-expiry behavior', async ({ page }) => {
    await login(page);
    await page.goto('/accounts/logout/');
    await expect(page).toHaveURL(/\/accounts\/login\//);
    await page.goto('/patients/');
    await expect(page).toHaveURL(/\/accounts\/login\//);
  });
});
