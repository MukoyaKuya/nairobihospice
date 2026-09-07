# Nairobi Hospice Palliative Care Management System (PCMS)
 
A secure, web-based clinical and operational platform for Nairobi Hospice.  

## Architecture
- **Backend**: Django 5.x Modular Monolith + PostgreSQL / SQLite fallback
- **Frontend**: Django Templates + HTMX + Alpine.js + Tailwind CSS
- **API**: Django REST Framework (v1) with OpenAPI / Swagger documentation
- **Background Jobs**: Celery + Redis (synchronous fallback in dev)
- **Deployment**: HostPinnacle / cPanel Python (Passenger WSGI) ready

## Quick Start (Development)
```bash
# Install dependencies
uv sync --extra dev

# Run migrations
uv run python manage.py migrate

# Seed realistic Kenyan clinical demo dataset
uv run python manage.py seed_hospice_data

# Run dev server
uv run python manage.py runserver
```

## Seeded development users

`seed_hospice_data` generates unique random passwords and prints them once to
the command output. Do not use seeded users or passwords in a shared or
production environment.

## API Documentation
- OpenAPI / Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Redoc UI: `http://127.0.0.1:8000/api/redoc/`
