# Screen House Guardian — Pilot Testing Guide

This guide covers everything a pilot coordinator needs to set up and run the
Phase 1A pilot with 10–30 tracking units in the screen house.

---

## 1. Prerequisites

- Screen House Guardian is deployed and accessible (local or server).
- You have superuser or Admin-group access.
- Tracking unit labels have been printed (A4 or label sheets — see Section 6).
- Participants have smartphones with a camera app that scans QR codes (iPhone
  default camera and most Android camera apps work without a separate app).

---

## 2. Create pilot users

### Step 1 — Open the Django admin

Go to `http://<your-server>/admin/` and log in with your superuser account.

### Step 2 — Create a new user

1. Click **Users → Add User**.
2. Enter a username (e.g. `observer_jane`) and a strong password.
3. Click **Save and continue editing**.
4. Fill in the **First name** and **Last name** fields if desired.
5. Leave **Staff status** and **Superuser status** unchecked for regular field staff.
6. Click **Save**.

Repeat for each pilot participant.

### Step 3 — Assign a group

Every user must belong to at least one role group before they can access the app.

1. In the user edit page, scroll down to **Groups**.
2. Select the appropriate group from the available list:
   - **Observer** — for field staff who only record observations.
   - **Manager** — for supervisors who also create units and export data.
   - **Admin** — for the IT/data lead (has Django admin access).
3. Click the right-arrow button to move the group to **Chosen groups**.
4. Click **Save**.

> **Tip:** The three groups (Observer, Manager, Admin) are created automatically
> by the initial database migration. You do not need to create them manually.

---

## 3. Create tracking units

### Option A — Using the management command (quick demo setup)

From the server terminal, inside the `screenhouse_guardian/` directory:

```bash
python manage.py create_demo_tracking_units
```

This creates four realistic demo units (Cassava, Taro, Banana, Kava) and prints
what was created or skipped. Run it again safely — it will not duplicate records.

### Option B — Using the Django admin (recommended for real pilot units)

1. Go to `http://<your-server>/admin/inventory/trackingunit/add/`.
2. Fill in the required fields:
   - **Unit code** — use a clear, unique code such as `TU-CAS-0001`.
   - **Unit type** — `container` for trays/pots, `individual` for single plants.
   - **Crop name** — free text (e.g. `Cassava`).
   - **Accession code** — free text (e.g. `CAS-ACC-001`), optional.
   - **Quantity** — number of plants in the container.
   - **Location text** — free text (e.g. `SH1 / Bench A`).
3. Leave **QR code** blank — it will be generated in the next step.
4. Click **Save**.

Repeat for each tracking unit you want to pilot (10–30 units recommended).

### Suggested unit code format

```
TU-<CROP-3-CHAR>-<SEQUENCE-4-DIGIT>
```

Examples: `TU-CAS-0001`, `TU-TAR-0001`, `TU-BAN-0001`, `TU-KAV-0001`

---

## 4. Generate QR labels

### Step 1 — Open the dashboard

Go to `http://<your-server>/dashboard/` (Manager or Admin role required).

### Step 2 — Generate QR for a unit

In the **Actions** column next to a unit that has no QR yet, click **Generate QR**.

The system will create a QR image pointing to the observation URL
(`/observe/<unit_code>/`) and save it. The page will then show a **QR label**
link for that unit.

### Step 3 — View and print the QR label

Click **QR label** in the dashboard action links for a unit.

The QR label page shows:
- The QR code image.
- The unit code and crop name.
- A print button (or use the browser print dialog).

> **Alternative:** Go directly to `/qr/units/<unit_code>/label/` for any unit
> with a generated QR code.

---

## 5. Print labels

### Printing from the browser

1. Open the QR label page for the unit.
2. Press **Ctrl+P** (Windows/Linux) or **Cmd+P** (Mac) to open the print dialog.
3. Set paper size to A4 or a label sheet size that matches your physical labels.
4. Disable headers/footers in the print options to get a clean label.
5. Print.

### Tips

- Print labels on adhesive label sheets (e.g. Avery A4) for field use.
- Laminate paper labels if the screen house is humid.
- Place labels on a visible, flat surface of the pot/tray (not on the soil).
- Keep a spare set of printed labels in case one is damaged.

---

## 6. Scan QR labels in the field

1. Open the phone camera app (no extra app required for iPhone or most Android).
2. Point the camera at the QR code on the label.
3. Tap the notification or banner that appears.
4. The browser opens directly to the observation form for that unit.

> If the QR code does not scan, ensure adequate lighting and hold the camera
> steady at 15–30 cm distance.

---

## 7. Submit an observation

After scanning a QR code and opening the observation form:

1. **Status** — select the plant condition:
   - Healthy, Watch, Sick, Critical, Dead, Recovered.
2. **Observation type** — `routine` for a standard check.
3. **Notes** — free text for anything notable (optional).
4. **Affected quantity** — number of plants showing the status (optional).
5. **Other fields** (growth stage, pest signs, water condition etc.) — fill in as
   relevant.
6. Tap **Save observation**.

A success message will appear and the page will redirect to the timeline.

---

## 8. Upload a photo

On the observation form, scroll down to the **Photo** section:

1. Tap **Choose file** (or the camera icon on mobile).
2. Select an existing photo from the gallery **or** use the phone camera to take
   a new photo.
3. Add an optional caption.
4. Submit the form normally — the photo uploads with the observation.

> **Note:** Photos must be JPEG or PNG and under the configured size limit.
> On slow connections, allow extra time for the upload before tapping Save.

---

## 9. Check the timeline

After submitting an observation you are redirected to the timeline automatically.

To navigate to the timeline directly:
- From the dashboard, click **Timeline** in the Actions column for any unit.
- From the observation form, click **Timeline** if shown.
- URL: `/observe/<unit_code>/timeline/`

The timeline shows all observations in reverse chronological order, with
status badges, photos, and a link to add a new observation.

---

## 10. Check the dashboard

Go to `http://<your-server>/dashboard/` (Observer role or higher).

The dashboard shows:

| Column | What it means |
|---|---|
| Active Units | Total active (not archived) tracking units |
| Total Quantity | Sum of all unit quantities |
| With QR Code | Units with a generated QR image |
| Without QR Code | Units still needing a QR — highlighted in orange |
| Checked Today | Units with an observation recorded today |
| Not Checked 7 Days | Units with no observation in the last 7 days |

The table shows each unit's latest observation status, last checked date, and
action links (QR label, Observe, Timeline).

---

## 11. Export data

Go to `http://<your-server>/exports/` (Manager or Admin role required).

Available exports:

| Export | Format | URL |
|---|---|---|
| Tracking units | CSV | `/exports/tracking-units.csv/` |
| Tracking units | Excel | `/exports/tracking-units.xlsx/` |
| Observations | CSV | `/exports/observations.csv/` |
| Observations | Excel | `/exports/observations.xlsx/` |
| Quantity events | CSV | `/exports/quantity-events.csv/` |
| Quantity events | Excel | `/exports/quantity-events.xlsx/` |

The **Export data** link is also available in the dashboard header bar for
Manager/Admin users.

---

## 12. Feedback to collect during the pilot

Ask participants to note the following after using the system in the field.

### Workflow speed

- How long did scanning and submitting one observation take?
- Was the form too long? Which fields were ignored?
- Did the keyboard on mobile make form entry awkward?

### Connectivity

- Did the form load reliably from inside the screen house?
- Were any submissions lost or timed out?
- Did photo uploads succeed on first try?

### QR labels

- Were QR codes easy to scan under screen house lighting?
- Did labels fall off or get damaged by humidity or watering?
- Were the labels large enough to scan from a comfortable distance?

### General usability

- Was the status vocabulary (Healthy, Watch, Sick, etc.) clear?
- Was it obvious what "quantity" meant for container units?
- Were there any confusing steps or missing information on the form?

### Data quality

- Were observers submitting observations at a consistent frequency?
- Were notes being written or left blank?
- Were photos being taken?

Collect feedback after 1–2 days of use and review the exported observation data
to identify gaps before the next pilot cycle.
