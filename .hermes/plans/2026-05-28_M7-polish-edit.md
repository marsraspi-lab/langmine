# M7: Polish & Edit

## Goal
Production-quality v1: manual overrides, error handling, empty/loading states, confirmation dialogs, settings page, theme toggle.

## Approach
Backend work first (new endpoints, error handling), then frontend (Svelte components).

## Step-by-Step

### 1. Backend — Edit Endpoints
- `PATCH /api/sentences/<id>` — update pinyin, translation_de, or text_segmented
- Re-segmentation triggers re-classification if `text_segmented` changes
- Return updated sentence

### 2. Backend — Config Endpoint
- `GET /api/config` — return current config (sanitized, no secrets)
- `PUT /api/config` — update config, write to config.yaml
- Need a `ConfigSaver` or just use the existing `load_config` + write logic

### 3. Backend — Better Error Responses
- Consistent error format: `{"error": "...", "detail": "..."}`
- Specific HTTP status codes
- Validation errors with field-level messages

### 4. Frontend — Toast/Notification System
- Toast component for success/error feedback
- Wire to API responses

### 5. Frontend — Click-to-Edit Fields
- Inline edit for pinyin, translation, segmented text
- Save on blur or Enter
- Show saving state

### 6. Frontend — Empty States
- "No videos yet" — suggest adding one
- "Stash is empty" — explain what it means
- "All caught up!" for 0 i+1

### 7. Frontend — Loading States
- Spinner overlay during video processing
- Progress bar (can poll /api/videos for status)

### 8. Frontend — Confirm Dialog
- Modal before delete/keep actions
- "Delete this sentence? Audio + screenshot will be removed."

### 9. Frontend — Settings Page
- New route/section for settings
- Form fields for all config values
- Save button

### 10. Frontend — Theme Toggle
- CSS variables for light/dark
- Toggle in header
- Persist to localStorage

## Files to Change
- `src/langmine/web/routes.py` — new/edit endpoints
- `src/langmine/config.py` — save_config function
- `src/langmine/web/frontend/src/lib/` — SentenceCard, CardList, new components
- `src/langmine/web/frontend/src/` — App.svelte, stores

## Tests
- Backend: new endpoints in test_web_api.py
- Frontend: Playwright E2E for edit flow, error states, settings
