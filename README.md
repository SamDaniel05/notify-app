# Notify (Vigil)

**Personal alert platform — watch what matters, get notified.**

Serious, news-style product. Public signup. English + Tamil. Free stack first.

## Stack

| Layer | Tech |
|--------|------|
| Backend | Django 5 + Django REST Framework + SimpleJWT |
| DB | SQLite (dev) / Postgres (prod) |
| Frontend | React (Vite) |
| Delivery | ntfy + Telegram |
| i18n | English + Tamil |

## Live

- Frontend (GitHub Pages): https://samdaniel05.github.io/notify-app/
- Backend: deploy free via Render using `render.yaml`

## Local

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install && npm run dev
```
