# EQi30 Backend

Django + Django REST Framework backend for the EQi-30 Emotional Intelligence app.

- Base URL: `/api/v1/`
- Auth: JWT Bearer tokens (SimpleJWT) — obtain via register/login, refresh via `/auth/token/refresh/`
- Interactive docs: `/api/docs/` (Swagger) · `/api/redoc/` (ReDoc)

## Setup

```bash
uv sync                                   # install dependencies
uv run python manage.py migrate
uv run python manage.py seed_eqi30       # 6 competencies, 30 abilities, plans, badges
uv run python manage.py seed_eqi30 --demo-content   # + placeholder day-1 lesson per ability
uv run python manage.py createsuperuser --noinput   # uses DJANGO_SUPERUSER_* from env
uv run python manage.py runserver
```

Configuration lives in `.env` (secret key, debug, SMTP for OTP emails, CORS).
Business-rule overrides: `ANONYMOUS_SESSION_TTL_MINUTES` (10), `PASSWORD_RESET_OTP_TTL_MINUTES` (10), `JOURNEY_TOTAL_DAYS` (30 — confirmed length; the 60-day Figma screen is not implemented).

## Main flow

1. `POST /onboarding/session/` → anonymous session (expires after 10 minutes unless claimed).
2. `POST /onboarding/{uuid}/assessment/` → AI developer submits scores + `ai_priority` per competency (all 6, priorities 1–6, no duplicates). `ai_priority` is never overwritten.
3. `PATCH /onboarding/{uuid}/priorities/` → accept AI order (`AI_RECOMMENDED`) or store a custom order (`CUSTOM`, saved separately as `user_priority`).
4. `PUT /onboarding/{uuid}/growth-plan/` + `PUT /onboarding/{uuid}/practice-time/`.
5. `POST /auth/register/` with `session_uuid` → user is created and the session is claimed **inside one transaction** (assessment + preferences attached, journey created, session marked `CLAIMED`). Expired sessions are deleted; registration still succeeds without the claim.
6. `GET /journey/` → six competency sections in the personalized order. `GET /journey/today/` → today's sessions.
7. `GET /abilities/{id}/days/{day}/` → lesson content; `POST /sessions/{id}/complete/` → updates progress/streak/badges; `POST /sessions/{id}/reflection/`, `POST /check-ins/weekly/`.
8. `GET /home/dashboard/`, `GET /progress/tracker/`, `GET /journey/history/`.

Run `uv run python manage.py purge_expired_sessions` from cron to clean up abandoned anonymous data (it is also purged opportunistically).

## Daily scheduling model

A journey lasts 30 days. The growth pace sets sessions per day (Low 1 / Medium 2 / High 3).
Day *d* covers global slots `[(d-1)·pace, d·pace)`; slot *i* maps to ability `order[i mod 30]`
with content day `i div 30 + 1` — every pace covers all 30 abilities at least once, faster
paces revisit abilities with day-2/day-3 content. The journey completes when the final day's
sessions are done (or the 30-day window ends).

## Other endpoints

| Area | Endpoints |
|---|---|
| Auth | `register` `login` `logout` `token/refresh` `forgot-password` `verify-otp` `resend-otp` `reset-password` `change-password` · `DELETE /user/account/` |
| Profile | `GET/PATCH /user/profile/` · `GET/PUT /user/reminders/` |
| Catalog | `GET /abilities/` `GET /guided-journey/` `GET /growth-plans/` `GET /practice-times/` |
| Subscription | `GET /subscription/plans/` `GET /subscription/status/` (store purchase verification deferred until the billing provider is confirmed) |
| Content | `GET /content/faqs/` `GET /content/privacy-policy/` `GET /content/terms-of-service/` |
| Feedback | `POST /feedback/` (multipart, optional attachment) |
| Resources | `GET /resources/?type=&competency=&favorites=` · `POST /resources/{id}/favorite/` |

All editable content (competencies, abilities, lessons, guided-journey images, badges, FAQs, legal documents, plans, resources) is managed through Django Admin at `/admin/`.

The AI chatbot itself is built by the AI developer — this backend only stores assessment output. `meditation` and `yoga` apps are intentionally empty placeholders until their screens are documented.

## Tests

```bash
uv run python manage.py test Apps
```

Covers the full onboarding → registration-claim → journey → completion → dashboard flow and the auth/OTP flows.
