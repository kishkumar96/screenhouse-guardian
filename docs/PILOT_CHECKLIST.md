# Screen House Guardian — Pilot Checklist

Use this checklist before, during, and after each pilot session to confirm the
core workflow is functioning correctly.

Mark each item: ✅ Pass | ❌ Fail | ⚠️ Partial | — Not tested

---

## Pre-pilot setup

| # | Task | Status | Notes |
|---|---|---|---|
| P1 | Pilot users created in Django admin | | |
| P2 | Users assigned to Observer or Manager group | | |
| P3 | At least 10 tracking units created | | |
| P4 | QR codes generated for all pilot units | | |
| P5 | QR labels printed and attached to pots/trays | | |
| P6 | App accessible from the screen house network | | |

---

## 1. Login test

**Goal:** Confirm users can log in and are denied if credentials are wrong.

| # | Step | Status | Notes |
|---|---|---|---|
| 1.1 | Open `/accounts/login/` in the browser | | |
| 1.2 | Enter valid username and password | | |
| 1.3 | Confirm redirect to home or dashboard after login | | |
| 1.4 | Enter wrong password — confirm error message shown | | |
| 1.5 | Confirm anonymous user cannot access `/dashboard/` (redirect to login) | | |

---

## 2. Dashboard test

**Goal:** Confirm the dashboard loads and shows accurate unit data.

| # | Step | Status | Notes |
|---|---|---|---|
| 2.1 | Log in as Observer and open `/dashboard/` | | |
| 2.2 | Confirm active units appear in the table | | |
| 2.3 | Confirm summary counts are visible (Active Units, Total Qty, etc.) | | |
| 2.4 | Confirm "Not checked" shown for units with no observations | | |
| 2.5 | Confirm archived units do NOT appear in the table | | |
| 2.6 | Log in as Manager — confirm **Export data** link is visible in dashboard | | |
| 2.7 | Log in as Observer — confirm **Export data** link is NOT visible | | |

---

## 3. QR label test

**Goal:** Confirm QR label page renders and contains correct unit information.

| # | Step | Status | Notes |
|---|---|---|---|
| 3.1 | Open `/qr/units/<unit_code>/label/` for a unit with a QR code | | |
| 3.2 | Confirm QR code image is displayed | | |
| 3.3 | Confirm unit code and crop name are shown on the label | | |
| 3.4 | Open browser print dialog — confirm label renders cleanly | | |
| 3.5 | As Manager: click **Generate QR** for a unit without a QR code | | |
| 3.6 | Confirm QR image is created and QR label page loads | | |
| 3.7 | As Observer: attempt POST to `/qr/units/<unit_code>/generate/` — confirm 403 | | |

---

## 4. Phone scan test

**Goal:** Confirm QR codes scan correctly on a real phone and open the
observation form.

| # | Step | Status | Notes |
|---|---|---|---|
| 4.1 | Pick up a phone and open the default camera app | | |
| 4.2 | Scan a printed QR label on a pot/tray | | |
| 4.3 | Confirm a banner or notification appears | | |
| 4.4 | Tap the banner and confirm `/observe/<unit_code>/` opens in the browser | | |
| 4.5 | Confirm unit code and crop name are shown at the top of the form | | |
| 4.6 | Confirm the form is readable on a small phone screen | | |

---

## 5. Observation submission test

**Goal:** Confirm a complete observation can be submitted and saved.

| # | Step | Status | Notes |
|---|---|---|---|
| 5.1 | Open the observation form for a unit | | |
| 5.2 | Select a **Status** (e.g. Healthy) | | |
| 5.3 | Leave all optional fields blank | | |
| 5.4 | Tap **Save observation** | | |
| 5.5 | Confirm success message appears | | |
| 5.6 | Confirm redirect to the timeline page | | |
| 5.7 | Confirm the observation appears in the timeline | | |
| 5.8 | Submit form with no status selected — confirm validation error shown | | |

---

## 6. Photo upload test

**Goal:** Confirm a photo can be uploaded with an observation.

| # | Step | Status | Notes |
|---|---|---|---|
| 6.1 | Open the observation form | | |
| 6.2 | Fill in Status field | | |
| 6.3 | Tap the photo/file field and choose an image from the gallery | | |
| 6.4 | Optionally add a caption | | |
| 6.5 | Submit the form | | |
| 6.6 | Confirm success message appears | | |
| 6.7 | Open the timeline and confirm the photo thumbnail is visible | | |
| 6.8 | Tap the thumbnail and confirm the full image opens | | |
| 6.9 | Try uploading a very large file (>5 MB) — confirm error message shown | | |

---

## 7. Timeline test

**Goal:** Confirm the timeline shows observations in order with full details.

| # | Step | Status | Notes |
|---|---|---|---|
| 7.1 | Open `/observe/<unit_code>/timeline/` for a unit with observations | | |
| 7.2 | Confirm observations appear in reverse chronological order | | |
| 7.3 | Confirm status badges are colour-coded | | |
| 7.4 | Confirm photos are shown as thumbnails | | |
| 7.5 | Confirm unit quantity and location are shown at the top of the page | | |
| 7.6 | Open the timeline for a unit with no observations | | |
| 7.7 | Confirm "No observations yet" message is shown | | |
| 7.8 | Confirm **Back to dashboard** link is visible and navigates correctly | | |

---

## 8. Export test

**Goal:** Confirm exports produce correct data files.

| # | Step | Status | Notes |
|---|---|---|---|
| 8.1 | Log in as Manager and open `/exports/` | | |
| 8.2 | Download Tracking Units CSV | | |
| 8.3 | Open CSV — confirm unit_code, crop_name, quantity columns are present | | |
| 8.4 | Download Observations Excel | | |
| 8.5 | Open Excel — confirm all submitted observations appear | | |
| 8.6 | Log in as Observer — confirm `/exports/` returns 403 | | |

---

## 9. Weak internet test

**Goal:** Confirm the app handles poor connectivity gracefully.

| # | Step | Status | Notes |
|---|---|---|---|
| 9.1 | Load the observation form while on WiFi | | |
| 9.2 | Turn off WiFi/mobile data on the phone | | |
| 9.3 | Fill in the form fields | | |
| 9.4 | Tap **Save observation** | | |
| 9.5 | Confirm the browser shows a network error (not a silent loss of data) | | |
| 9.6 | Re-enable connectivity and resubmit the form | | |
| 9.7 | Confirm the observation is saved successfully | | |

---

## 10. Logout test

**Goal:** Confirm users can log out cleanly and protected pages are locked.

| # | Step | Status | Notes |
|---|---|---|---|
| 10.1 | Click **Logout** in the navigation bar | | |
| 10.2 | Confirm redirect to home or login page | | |
| 10.3 | Attempt to navigate to `/dashboard/` while logged out | | |
| 10.4 | Confirm redirect to login page | | |

---

## Post-pilot review

After completing the pilot session:

- [ ] Export all observations and review for data quality issues.
- [ ] Note which fields were frequently left blank.
- [ ] Note how long each observation took (ask participants).
- [ ] Check for any QR label damage or scanning failures.
- [ ] Collect verbal or written feedback from participants.
- [ ] Summarise findings and update the project backlog.
