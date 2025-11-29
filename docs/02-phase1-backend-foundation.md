# 02 – Phase 1: Backend Foundation

## 1. Goal

Menyiapkan fondasi backend yang bersih:

- Struktur folder FastAPI rapi.
- SQLite + SQLAlchemy + Alembic berjalan.
- Basic `User` model + auth JWT.
- Health check endpoint.
- Tanpa fitur AI dulu.

## 2. Deliverables

- App FastAPI bisa run dengan `uvicorn app.main:app`.
- Database `app.db` dengan tabel `users` & `ai_usage_logs` minimal.
- Endpoint:
  - `POST /auth/register`
  - `POST /auth/login`
  - `GET /me`
  - `GET /health`

## 3. Struktur Direktori Backend

Contoh:

```txt
backend/
  app/
    core/
      config.py
      security.py
    db/
      base.py
      session.py
    models/
      user.py
      ai_usage_log.py
    schemas/
      user.py
      auth.py
    api/
      deps.py
      routes/
        auth.py
        users.py
        health.py
    main.py
  alembic/
  alembic.ini

4. Dependencies

Tambahkan ke pyproject.toml / requirements.txt:

    fastapi

    uvicorn[standard]

    sqlalchemy

    alembic

    pydantic

    passlib[bcrypt]

    python-jose[cryptography]

    python-multipart

5. Data Model
5.1. User

Field minimal:

    id: int

    email: str (unique)

    password_hash: str

    created_at: datetime

    is_active: bool

    credits: int (untuk future credit system)

5.2. AIUsageLog (minimal)

    id

    user_id

    provider (openai, dll)

    model

    tokens_input

    tokens_output

    created_at

6. API Contracts
6.1. POST /auth/register

Body:

    email

    password

Response:

    user info (id, email, created_at)

    access token (opsional, atau login terpisah)

6.2. POST /auth/login

Body:

    email

    password

Response:

    access_token

    token_type

6.3. GET /me

Header:

    Authorization: Bearer <token>

Response:

    user data + credits.

6.4. GET /health

Simple JSON: { "status": "ok" }.
7. Testing Checklist

    ✅ Bisa register & login.

    ✅ JWT valid & kadaluarsa.

    ✅ SQLite file muncul & schema sesuai.

    ✅ Dokumen ini diupdate jika ada perubahan model penting.

8. Next

Phase 2 akan menambahkan tabel video_sources, processing_jobs dan endpoint upload/link.