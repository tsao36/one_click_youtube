---
name: ui-validator
description: Automatically validates user interface changes in a browser after modifying frontend components, HTML, CSS, Tailwind, or layout code. Use this skill every time a UI update is made before concluding a task.
---

# Automated UI Validation Workflow

Whenever you create or modify user interface code, you must verify the rendered output before finishing your turn. Do not ask the user to manually check the browser.

## Prerequisites & Setup
1. Check if the local development server is already running (e.g., via `lsof -i :3000` or checking active terminal processes).
2. If the dev server is not running, start it in the background (e.g., `npm run dev`) and wait until the port is listening.

## Verification Steps
1. **Launch Browser Subagent / Browser Tool:** Navigate to the local URL and specific route affected by the UI change.
2. **Console & Network Check:** Inspect browser console logs and network requests. Fail immediately if there are uncaught React/JS runtime errors, hydration mismatches, or 404/500 asset errors.
3. **Functional & Layout Verification:**
   - Verify that newly added or modified elements are visible in the DOM and not clipped, overlapping, or overflowing the viewport.
   - If the change involves interactive elements (buttons, forms, modals, toggles), simulate clicking or typing into them to verify state transitions.
   - Check both desktop (`1280x800`) and mobile (`375x812`) viewport widths if layout/responsive styles were touched.
4. **Visual Evidence:** Capture a screenshot of the verified state and save it to `.artifacts/ui-check.png` (or attach it as a workspace Artifact).

## Completion Criteria
- If any console error, broken layout, or failed interaction is detected, fix the code and re-run this validation loop.
- Only report the task complete to the user once visual and functional verification passes.