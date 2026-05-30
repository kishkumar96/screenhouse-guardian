# Phase 1A Phone Test 001

## Date
2026-05-30

## Objective
Run a fuller Phase 1A pilot covering the end-to-end QR workflow with multiple
units, multiple observations, photo uploads, exports, and real-world field
checks.

## Scope

1. Create 10 tracking units.
2. Create Manager and Observer users.
3. Generate QR labels as Manager.
4. Print/display QR labels.
5. Scan with phone as Observer.
6. Submit 10+ observations.
7. Upload 5+ photos.
8. Check dashboard.
9. Check timelines.
10. Export data.
11. Test weak internet.
12. Test QR durability.
13. Write pilot notes.

## Preconditions

- App is reachable from the phone on the same network.
- `DEBUG=True` for local pilot use if static files depend on Django dev serving.
- Observer, Manager, and Admin groups exist.
- At least one Manager login and one Observer login are available.
- Printer or display method is available for QR labels.

## Pilot operators

- Manager user:
- Observer user:
- Device(s) used:
- Network used:

## Execution checklist

Mark each item: `PASS`, `FAIL`, `PARTIAL`, or `NOT TESTED`.

| # | Task | Status | Notes / evidence |
|---|---|---|---|
| 1 | Create 10 tracking units |  |  |
| 2 | Create Manager and Observer users |  |  |
| 3 | Generate QR labels as Manager |  |  |
| 4 | Print/display QR labels |  |  |
| 5 | Scan with phone as Observer |  |  |
| 6 | Submit 10+ observations |  |  |
| 7 | Upload 5+ photos |  |  |
| 8 | Check dashboard |  |  |
| 9 | Check timelines |  |  |
| 10 | Export data |  |  |
| 11 | Test weak internet |  |  |
| 12 | Test QR durability |  |  |
| 13 | Write pilot notes |  |  |

## Detailed record

### 1. Tracking units created

- Count created:
- Example unit codes:
- Any creation issues:

### 2. Users created

- Manager username:
- Observer username:
- Group assignment confirmed:

### 3. QR generation

- Units with QR generated:
- Any failed generations:
- Did QR generation return to the dashboard when triggered there:

### 4. QR label display / print

- Displayed on screen:
- Printed physically:
- Label size / format used:
- Print quality acceptable:

### 5. Phone scan test

- Phone model(s):
- Camera app used:
- Did scans open `/observe/<unit_code>/` directly:
- Any scan failures or slow scans:

### 6. Observation submission

- Number of observations submitted:
- Status values tested:
- Did success redirect to timeline consistently:
- Validation issues encountered:

### 7. Photo upload

- Number of photo uploads:
- Approximate photo sizes:
- Thumbnail shown in timeline:
- Full image opened correctly:
- Any upload failures:

### 8. Dashboard review

- Active unit counts looked correct:
- Checked today count updated:
- QR label / Observe / Timeline actions worked:
- Any mismatch noted:

### 9. Timeline review

- Unit timelines checked:
- Reverse chronological ordering correct:
- Photos and notes displayed:
- Correction behaviour tested:

### 10. Export review

- Export formats tested:
- Files opened successfully:
- Observations present:
- Photos metadata present if expected:
- Any column/data issues:

### 11. Weak internet test

- Method used:
- Behaviour during degraded connectivity:
- Was data loss prevented:
- Was user feedback clear:

### 12. QR durability test

- Label material:
- Humidity exposure:
- Water / abrasion exposure:
- Still scannable after exposure:
- Reprint needed:

### 13. Pilot notes

#### What worked well

- 

#### Problems found

- 

#### User feedback

- 

#### Recommended follow-up

- 

## Result summary

- Overall result:
- Ready for broader pilot:
- Blocking issues:

## Outcome

Pending execution.

## Notes

This document is a real-world pilot record. Items 4, 5, 11, and 12 require
physical/manual testing and cannot be validated purely from automated tests.
