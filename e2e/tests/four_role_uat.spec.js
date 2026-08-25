const { test, expect } = require('@playwright/test');

/**
 * Nairobi Hospice PCMS: 4-Role End-to-End User Acceptance Test (UAT) & Authorization Matrix
 *
 * Workflow:
 * 1. Receptionist: Intake & register patient with care team assignment (No clinical fields).
 * 2. Nurse: Submit ESAS symptom assessment for assigned patient.
 * 3. Doctor: Complete clinical consultation encounter & prescribe morphine statement.
 * 4. Pharmacist: Record dispense FIRST (caseload is dispense-based), THEN open patient detail.
 * 5. Role Boundary & 403 Exclusion Checks.
 *
 * Passwords are read from the environment. There are no hardcoded credential defaults.
 * Set UAT_RECEPTION_PASSWORD, UAT_NURSE_PASSWORD, UAT_DOCTOR_PASSWORD, UAT_PHARMACIST_PASSWORD
 * (PCMS_E2E_*_PASSWORD is accepted as a CI fallback). fullyParallel remains false in playwright.config.js.
 */

const BASE_URL = process.env.PCMS_E2E_BASE_URL || 'http://127.0.0.1:8009';

function envCredential(primary, fallback) {
  const value = process.env[primary] || process.env[fallback];
  return value && String(value).trim() ? String(value) : '';
}

const ROLES = {
  receptionist: {
    email: envCredential('UAT_RECEPTION_EMAIL', 'PCMS_E2E_RECEPTION_EMAIL') || 'receptionist@nairobihospice.or.ke',
    password: envCredential('UAT_RECEPTION_PASSWORD', 'PCMS_E2E_RECEPTION_PASSWORD'),
  },
  nurse: {
    email: envCredential('UAT_NURSE_EMAIL', 'PCMS_E2E_NURSE_EMAIL') || 'nurse@nairobihospice.or.ke',
    password: envCredential('UAT_NURSE_PASSWORD', 'PCMS_E2E_NURSE_PASSWORD'),
  },
  doctor: {
    email: envCredential('UAT_DOCTOR_EMAIL', 'PCMS_E2E_DOCTOR_EMAIL') || 'doctor@nairobihospice.or.ke',
    password: envCredential('UAT_DOCTOR_PASSWORD', 'PCMS_E2E_DOCTOR_PASSWORD'),
  },
  pharmacist: {
    email: envCredential('UAT_PHARMACIST_EMAIL', 'PCMS_E2E_PHARMACIST_EMAIL') || 'pharmacist@nairobihospice.or.ke',
    password: envCredential('UAT_PHARMACIST_PASSWORD', 'PCMS_E2E_PHARMACIST_PASSWORD'),
  },
};

const missingPasswords = Object.entries(ROLES)
  .filter(([, creds]) => !creds.password)
  .map(([role]) => role);

async function loginUser(page, roleCredentials) {
  await page.goto(`${BASE_URL}/accounts/login/`);
  await page.fill('input[name="username"], input[name="email"]', roleCredentials.email);
  await page.fill('input[name="password"]', roleCredentials.password);
  await page.click('button[type="submit"]');
  await expect(page).not.toHaveURL(/\/accounts\/login\//);
}

async function logoutUser(page) {
  await page.goto(`${BASE_URL}/accounts/logout/`);
  const logoutBtn = page.locator('button[type="submit"]');
  if (await logoutBtn.count()) {
    await logoutBtn.click();
  }
}

test.describe.configure({ mode: 'serial' });

test.describe('Nairobi Hospice PCMS: 4-Role UAT & Authorization Suite', () => {
  test.skip(
    missingPasswords.length > 0,
    `Set UAT_*_PASSWORD (or PCMS_E2E_*_PASSWORD) for: ${missingPasswords.join(', ')}`,
  );

  let patientId = null;

  test('Step 1: Receptionist - Patient Intake & Registration (Bio-Data only)', async ({ page }) => {
    await loginUser(page, ROLES.receptionist);

    await page.goto(`${BASE_URL}/reporting/clinical/`);
    await expect(page.locator('body')).not.toContainText('Pain Spikes');

    await page.goto(`${BASE_URL}/patients/register/`);
    await page.fill('input[name="first_name"]', 'UAT');
    await page.fill('input[name="last_name"]', 'Careflow');
    await page.selectOption('select[name="sex"]', 'F');
    await page.fill('input[name="date_of_birth"]', '1982-06-15');
    await page.fill('input[name="phone_number"]', '0712345678');
    await page.fill('input[name="county"]', 'Nairobi');
    await page.fill('input[name="sub_county"]', 'Kibra');

    const nurseSelect = page.locator('select[name="primary_nurse"]');
    if (await nurseSelect.count()) {
      await nurseSelect.selectOption({ index: 1 });
    }
    const docSelect = page.locator('select[name="primary_doctor"]');
    if (await docSelect.count()) {
      await docSelect.selectOption({ index: 1 });
    }

    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/patients\/[^/]+\//);

    const url = page.url();
    const matches = url.match(/\/patients\/([^/]+)\//);
    if (matches) {
      patientId = matches[1];
    }

    await expect(page.locator('body')).not.toContainText('Clinical Encounters');
    await expect(page.locator('body')).not.toContainText('ESAS Symptom Tracker');
  });

  test('Step 2: Nurse - Record ESAS Symptom Assessment', async ({ page }) => {
    test.skip(!patientId, 'Patient must be created in Step 1');
    await logoutUser(page);
    await loginUser(page, ROLES.nurse);

    await page.goto(`${BASE_URL}/symptoms/patient/${patientId}/create/`);
    await expect(page.locator('h1, h2')).toContainText(/ESAS|Symptom/i);

    await page.fill('input[name="pain"]', '6');
    await page.fill('input[name="tiredness"]', '4');
    await page.fill('input[name="nausea"]', '2');
    await page.fill('input[name="depression"]', '3');
    await page.fill('input[name="anxiety"]', '4');
    await page.fill('input[name="drowsiness"]', '1');
    await page.fill('input[name="appetite"]', '5');
    await page.fill('input[name="wellbeing"]', '6');
    await page.fill('input[name="shortness_of_breath"]', '2');

    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/`));
    await expect(page.locator('body')).toContainText(/ESAS|Symptom Score/i);
  });

  test('Step 3: Doctor - Clinical Consultation & Prescribe Morphine', async ({ page }) => {
    test.skip(!patientId, 'Patient must be created in Step 1');
    await logoutUser(page);
    await loginUser(page, ROLES.doctor);

    await page.goto(`${BASE_URL}/encounters/patient/${patientId}/create/`);
    await page.selectOption('select[name="encounter_type"]', 'CLINIC_VISIT');
    await page.fill('textarea[name="clinical_notes"]', 'Patient presented with breakthrough pain. Initiating oral morphine syrup.');
    await page.click('button[type="submit"]');

    await page.goto(`${BASE_URL}/medications/patient/${patientId}/prescribe/`);
    await page.fill('input[name="medication_name"]', 'Oral Morphine Solution 10mg/5ml');
    await page.fill('input[name="dosage"]', '5mg');
    await page.selectOption('select[name="route"]', 'ORAL');
    await page.fill('input[name="frequency"]', 'q4h prn');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/`));
    await expect(page.locator('body')).toContainText(/Oral Morphine/i);
  });

  test('Step 4: Pharmacist - Dispense first, then patient detail', async ({ page }) => {
    test.skip(!patientId, 'Patient must be created in Step 1');
    await logoutUser(page);
    await loginUser(page, ROLES.pharmacist);

    // Dispense first so pharmacist caseload exists. Opening patient detail before a
    // recorded dispense returns 404 because authorized_patient_queryset is dispense-based.
    await page.goto(`${BASE_URL}/operations/pharmacy/dispense/?patient=${patientId}`);
    const patientSelect = page.locator('select[name="patient"]');
    if (await patientSelect.count()) {
      const option = patientSelect.locator(`option[value="${patientId}"]`);
      if (await option.count()) {
        await patientSelect.selectOption(patientId);
      }
    }
    const stockSelect = page.locator('select[name="stock_item"]');
    if (await stockSelect.count()) {
      await stockSelect.selectOption({ index: 1 });
    }
    const rxSelect = page.locator('select[name="medication_statement"]');
    if (await rxSelect.count()) {
      await rxSelect.selectOption({ index: 1 });
    }
    await page.fill('input[name="quantity"]', '2');
    await page.fill('textarea[name="notes"]', 'Dispensed 2 bottles oral morphine for pain regimen');
    await page.click('button[type="submit"]');

    await page.goto(`${BASE_URL}/patients/${patientId}/`);
    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/`));
    await expect(page.locator('body')).toContainText(/Oral Morphine/i);
    await expect(page.locator('body')).not.toContainText('Initiating oral morphine syrup');
  });

  test('Step 5: Fail-Closed Authorization Boundary Checks (403 Enforcement)', async ({ page }) => {
    test.skip(!patientId, 'Patient must be created in Step 1');
    await logoutUser(page);

    await loginUser(page, ROLES.pharmacist);
    const pharmEditResp = await page.goto(`${BASE_URL}/patients/${patientId}/edit/`);
    expect(pharmEditResp.status()).toBe(403);

    const pharmRegResp = await page.goto(`${BASE_URL}/patients/register/`);
    expect(pharmRegResp.status()).toBe(403);

    const pharmRoutesResp = await page.goto(`${BASE_URL}/appointments/routes/`);
    expect(pharmRoutesResp.status()).toBe(403);

    await logoutUser(page);
    await loginUser(page, ROLES.receptionist);

    const recEncounterResp = await page.goto(`${BASE_URL}/encounters/patient/${patientId}/create/`);
    expect(recEncounterResp.status()).toBe(403);

    const recSymptomsResp = await page.goto(`${BASE_URL}/symptoms/patient/${patientId}/create/`);
    expect(recSymptomsResp.status()).toBe(403);

    const recDocUploadResp = await page.goto(`${BASE_URL}/documents/patient/${patientId}/upload/`);
    expect(recDocUploadResp.status()).toBe(403);
  });
});
