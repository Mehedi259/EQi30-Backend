# EQi30 Backend Repository

Welcome to the backend repository for the **EQi-30 Emotional Intelligence** application!

This repository hosts the robust API backend that powers the EQi-30 mobile application, designed to help users build their emotional intelligence through personalized journeys, daily lessons, and practice tracking.

## 🏗 Project Structure

- `services/backend/` - The core Django application, built with Django REST Framework (DRF) and managed using the blazing fast `uv` package manager.
- `infrastructure/` - Infrastructure configuration and deployment scripts (if applicable).

## 🚀 Quick Start (Backend Service)

To get the backend running locally, navigate to the `services/backend/` directory and use `uv` to setup your environment.

```bash
cd services/backend

# 1. Install dependencies
uv sync

# 2. Apply database migrations
uv run python manage.py migrate

# 3. Seed initial data (competencies, abilities, plans, etc.)
uv run python manage.py seed_eqi30

# Optional: Seed with demo content for testing
uv run python manage.py seed_eqi30 --demo-content

# 4. Create an admin user (uses DJANGO_SUPERUSER_* from your .env)
uv run python manage.py createsuperuser --noinput

# 5. Start the development server
uv run python manage.py runserver
```

## 📖 API Documentation & Details

The backend provides:
- **Base URL:** `/api/v1/`
- **Authentication:** JWT Bearer tokens (via SimpleJWT)
- **Interactive Docs:** Accessible at `/api/docs/` (Swagger) and `/api/redoc/`

For comprehensive details on the API endpoints, daily scheduling model, main onboarding/registration flows, and how to run tests, please see the [detailed Backend README](./services/backend/README.md).
