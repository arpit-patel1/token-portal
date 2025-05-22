**API Token Management Portal - Combined Design Document (2-Week MVP Focus)**

---

## 0. MVP Scope & Timeline

This document has been revised to highlight features planned for an initial **2-Week Minimum Viable Product (MVP)**.
Features marked `[MVP]` are targeted for this sprint.
Features marked `[POST-MVP]` are planned for subsequent iterations.
The goal is to deliver core functionality for user authentication, API token management by users, and basic API token validation within the 2-week timeframe.

---

## 1. Overview

This document outlines the design for an API Token Management Portal. The portal will allow users in a local lab environment (approximately 500 users, non-concurrent usage) to sign in using their email address and a One-Time Password (OTP), generate API tokens with optional expiration dates, and manage these tokens `[MVP]`. These tokens will be used to authenticate access to specific APIs served under the `/api/public/*` URI `[MVP]`. The system will also support admin users who can monitor API usage (basic logs `[MVP]`) and manage users (basic views `[MVP]`). This design prioritizes open-source tools and local deployment.

---

## 2. Architecture

The system will be composed of the following main components, containerized using Docker for local deployment:

*   **Frontend:** A React Single-Page Application (SPA) providing the user interface for authentication, token management `[MVP]`, and admin functionalities (basic `[MVP]`).
*   **Backend:** An asynchronous API built with FastAPI (Python) that handles business logic, user authentication (email OTP `[MVP]`), token generation/management `[MVP]`, API request validation `[MVP]`, and database interactions `[MVP]`.
*   **Database:**
    *   A PostgreSQL database (asynchronous access) to store user information, API token primary metadata, and API usage logs `[MVP]`.
    *   A Redis instance for storing OTP details and caching API token data for fast validation `[MVP]`.

**Deployment:** `[MVP]`

*   Docker and Docker Compose will be used for packaging and managing the services (frontend, backend, PostgreSQL, Redis) in the local lab environment.
*   A reverse proxy (e.g., Nginx) is recommended for handling incoming requests, SSL termination, and serving static frontend assets.

---

## 3. Backend (FastAPI)

### 3.1. Project Structure (Conceptual) `[MVP]`

```
app/
├── main.py             # FastAPI app initialization, middleware
├── api/
│   ├── v1/
│   │   ├── endpoints/
│   │   │   ├── auth.py         # Sign-in, OTP
│   │   │   ├── tokens.py       # User token management
│   │   │   ├── admin.py        # Admin functionalities
│   │   │   └── public_api_proxy.py # Handles /api/public/*
│   │   └── schemas.py      # Pydantic models for v1
├── core/
│   ├── config.py         # Settings (database URL, JWT secret, email config)
│   ├── security.py       # Hashing, JWT creation, API key validation
│   └── dependencies.py   # Common dependencies (DB session, user auth)
├── db/
│   ├── base.py           # SQLAlchemy base and engine setup (async)
│   ├── models.py         # SQLAlchemy ORM models
│   ├── crud.py           # CRUD operations for models (async)
│   └── session.py        # Async session management
└── services/
    ├── email_service.py  # Logic for sending OTP emails via Gmail
    ├── otp_service.py    # OTP generation and verification logic (using Redis)
    └── redis_service.py  # Redis connection and utility functions
```

### 3.2. API Routers & Key Endpoints `[MVP]`

| Router        | Path Prefix     | Key Endpoints                                       | Description                                      |
| ------------- | --------------- | --------------------------------------------------- | ------------------------------------------------ |
| Auth          | `/api/v1/auth`  | `POST /request-otp`, `POST /verify-otp`             | Email & OTP login, JWT issuance.                 |
| Users         | `/api/v1/users` | `GET /me`                                           | Authenticated user profile info.                 |
| Tokens        | `/api/v1/tokens`| `POST /`, `GET /`, `DELETE /{token_id}`             | API Token management (CRUD) for the current user.|
| Public API    | `/api/v1/public`| `ANY /{path:path}` (e.g., `GET /ping`)              | API endpoints protected by generated API tokens. |
| Admin         | `/api/v1/admin` | `GET /users`, `GET /tokens`, `GET /usage/logs` (basic) | Admin-only: basic user & token lists, raw logs. `[POST-MVP]` for `GET /users/{user_id}`, `GET /usage/summary`. |

### 3.3. Authentication Flow `[MVP]`

1.  **Email Submission:**
    *   User enters their email address in the React frontend.
    *   Frontend calls `POST /auth/request-otp` with the email.
2.  **OTP Generation & Sending:**
    *   Backend generates a cryptographically secure 5-digit OTP.
    *   The OTP is hashed (e.g., using SHA256).
    *   The `user_email`, `otp_hash`, and an `expires_at` timestamp (e.g., 5-10 minutes) are stored in Redis with an appropriate expiry time.
    *   The plain OTP is sent to the user's email address using `smtp.gmail.com`. This will require configuring FastAPI with a Gmail account and an "App Password".
3.  **OTP Verification:**
    *   User receives the OTP via email and submits it through the React frontend.
    *   Frontend calls `POST /auth/verify-otp` with the email and the submitted OTP.
    *   Backend retrieves the `otp_hash` for the given email from Redis.
    *   It hashes the submitted OTP and compares it with the stored hash. It also implicitly checks for expiration (as Redis would have auto-deleted expired keys) and if the OTP has already been marked as used (e.g., by deleting it from Redis upon successful verification).
    *   If valid, the OTP record is typically deleted from Redis to prevent reuse.
4.  **Session Establishment:**
    *   Upon successful OTP verification, a JSON Web Token (JWT) is generated.
    *   The JWT contains user ID, email, role (user/admin), and an expiration time.
    *   The JWT is returned to the frontend to be used for authenticating subsequent requests to protected portal endpoints.

### 3.4. API Key Handling (for `/api/public/*`) `[MVP]`

*   **Generation:** API tokens are generated by users from the `/tokens` endpoint. They will be long, random, and unique strings (e.g., UUIDv4 or cryptographically secure random string).
*   **Display:** The raw API token is displayed to the user **only once** upon creation.
*   **Storage:**
    *   A hash (e.g., SHA256) of the API token is stored in the `api_tokens` table in PostgreSQL (as the source of truth for metadata).
    *   For fast validation, key information (e.g., `user_id`, `expires_at`, `revoked` status) associated with the hashed token is also stored in Redis, keyed by the `hashed_token`.
    *   The raw token is never stored.
*   **Metadata:** Stored metadata in PostgreSQL includes user ID, a user-defined name, creation date, expiration date (optional), and a revoked flag.
*   **Validation:** A FastAPI middleware will protect all routes under `/api/public/*`.
    *   It will extract the API token from the request header (e.g., `X-API-Key` or `Authorization: Bearer <api_token>`).
    *   The provided token will be hashed. The backend will first query Redis using this hash to check for the token's existence, validity (not expired, not revoked).
    *   If not found in Redis or invalid, access is denied.
    *   If found and valid in Redis, the request proceeds. The `user_id` from the Redis cache can be used for logging.
    *   The primary `api_tokens` table in PostgreSQL is still the source of truth. Updates to token status (e.g., revocation) must be reflected in both PostgreSQL and Redis.
    *   API usage will be logged (basic details `[MVP]`).

### 3.5. Access Control `[MVP]`

*   **JWT:** Required for accessing `/users`, `/tokens`, and `/admin` endpoints. The JWT will contain the user's role, enforced by dependencies on protected routes.
*   **API Key:** Required exclusively for accessing `/api/public/*` endpoints. API Keys are not valid for portal access.
*   **Secrets Management:** Store database credentials, JWT secrets, email App Password, Redis connection details, etc., using environment variables.
*   **Regular Updates:** `[POST-MVP]` for ongoing maintenance, but use up-to-date libraries for initial build.
*   **Extensive Security Hardening & Audits:** `[POST-MVP]`

### 3.6. Admin Capabilities

*   `[MVP]` View a list of all users (displaying email, role).
*   `[MVP]` View a list of all API tokens (metadata only: name, user email, creation/expiry dates, revoked status).
*   `[MVP]` View raw API usage logs (simple tabular display, basic filtering if time allows).
*   `[POST-MVP]` View detailed information for a specific user (`GET /admin/users/{user_id}`).
*   `[POST-MVP]` View API usage summary statistics (`GET /admin/usage/summary`) and charts.
*   `[POST-MVP]` Admin ability to revoke user tokens or deactivate users directly through the UI (can be done via DB in lab for MVP if essential).

---

## 4. Database Schema (PostgreSQL - Asynchronous) `[MVP]`

SQLAlchemy with its asyncio extension will be used as the ORM for PostgreSQL. Redis will be used for OTPs and API token validation caching.

### 4.1. `users` Table `[MVP]`

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY, -- Or UUID
  email TEXT UNIQUE NOT NULL,
  role TEXT CHECK (role IN ('user', 'admin')) NOT NULL DEFAULT 'user',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Auto-update on change
  is_active BOOLEAN DEFAULT TRUE,
  last_login_at TIMESTAMP WITH TIME ZONE NULL
);
```
*Indexes: `email`, `role`.*

### 4.2. `auth_otp` Table (Replaces Redis for OTP storage) `[MVP]`

This table will be **removed**. OTPs will be stored in Redis.

### 4.3. `api_tokens` Table `[MVP]`

This table remains the primary source of truth for API token metadata. Redis will be used to cache essential data for fast validation lookups.
```sql
CREATE TABLE api_tokens (
  id SERIAL PRIMARY KEY, -- Or UUID
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  name TEXT, -- User-defined name for the token
  hashed_token TEXT UNIQUE NOT NULL, -- Hash of the full API token
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE, -- Nullable if tokens can be non-expiring
  last_used_at TIMESTAMP WITH TIME ZONE NULL,
  revoked BOOLEAN DEFAULT FALSE, -- For user/admin revocation
  usage_count INT DEFAULT 0 -- `[POST-MVP]` (if detailed admin stats are deferred)
);
```
*Indexes: `user_id`, `hashed_token`, `expires_at`, `revoked`.*

### 4.4. `api_usage_logs` Table `[MVP]`

```sql
CREATE TABLE api_usage_logs (
  id BIGSERIAL PRIMARY KEY, -- Or UUID
  api_token_id INT REFERENCES api_tokens(id) ON DELETE SET NULL, -- Nullable to log attempts with invalid tokens
  user_id INT REFERENCES users(id) ON DELETE SET NULL, -- Can be derived from token_id, or from Redis cache during validation
  request_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  request_method VARCHAR(10) NOT NULL,
  request_path TEXT NOT NULL,
  response_status_code INT NOT NULL,
  processing_time_ms INT NULL,
  client_ip_address TEXT NULL, -- Consider privacy implications
  user_agent TEXT NULL -- Consider privacy implications
);
```
*Indexes: `api_token_id`, `user_id`, `request_timestamp`, `request_path`, `response_status_code`.*
*(Consider partitioning for very high traffic: `[POST-MVP]`)*.

---

## 5. Frontend (React)

### 5.1. Design Aesthetic: "Black on Silver" (Apple-Inspired)

*   `[MVP]` **Color Palette:**
    *   Primary Backgrounds ("Silver"): Light grays and off-whites (e.g., `#F5F5F7`).
    *   Text & Key Accents ("Black"): Deep, rich black or very dark gray for text (e.g., `#1D1D1F`).
    *   Secondary Grays: For basic UI element distinction.
    *   Optional Accent: A subtle blue like `#007AFF` for links/focus.
*   `[MVP]` **Typography:**
    *   Font: "Inter" or similar clean sans-serif.
    *   Basic hierarchy (headings, body text).
    *   Good readability with adequate spacing.
*   `[MVP]` **Layout & Spacing:**
    *   Clean, uncluttered with sufficient white space.
    *   Consistent basic grid/alignment.
*   `[MVP]` **UI Elements:**
    *   Functional buttons, forms, and containers with minimal styling adhering to the theme.
    *   Simple line-style SVG icons.
*   `[POST-MVP]` Highly polished details, complex gradients, subtle shadows, advanced animations, glassmorphism.
*   **Implementation:** `[MVP]`
    *   CSS Custom Properties for theme variables.
    *   Styling: CSS Modules or a utility-first framework like Tailwind CSS (configured for the basic theme) to expedite. Styled-components are fine if the developer is fast with them.
    *   Consider a minimal component library or build very simple custom components. Headless UI for specific complex interactions if essential and time allows for styling.

### 5.2. Pages / Views `[MVP]`

*   **Login Page:** Email input for OTP request.
*   **OTP Verification Page:** Input for the 5-digit OTP.
*   **User Dashboard:**
    *   View, manage, and revoke existing API tokens (masked token, name, expiry, status).
    *   Button to "Create New Token".
*   **Token Creation Modal/Page:**
    *   Input for token name (optional).
    *   Input for expiration date (optional, calendar picker).
    *   **Crucially, display the generated API token to the user ONCE, with clear instructions to copy and save it securely.**
*   **Admin Panel (Admin users only):** `[MVP]`
    *   Navigation to User Management and API Usage Monitoring.
    *   **User Management Page:** Simple table list of users (email, role).
    *   **Token Management Page (Admin):** Simple table list of all tokens (metadata).
    *   **API Usage Monitoring Page:** Simple table view of raw API usage logs.
    *   `[POST-MVP]` Charts, advanced filtering, and data visualization.

### 5.3. Key Libraries & State Management `[MVP]`

*   **Routing:** React Router (`react-router-dom`).
*   **API Calls:** Axios or `fetch` API.
*   **Server State Management:** React Query or SWR (highly recommended for MVP).
*   **Global State (Optional):** React Context API for basic auth status/user info.
*   **UI Components:** As per 5.1, prioritize speed and functionality.
*   **Charting (for Admin Panel):** `[POST-MVP]` (e.g., Chart.js, Recharts).

---

## 6. Security `[MVP]`

*   **HTTPS:** Enforce HTTPS. For local lab deployment, use self-signed certificates or Let's Encrypt if externally accessible. Nginx can handle SSL termination.
*   **Email (OTP via Gmail):**
    *   Use a dedicated Gmail account for sending OTPs.
    *   Enable 2-Step Verification on this Gmail account.
    *   Generate and use an **App Password** in the FastAPI backend configuration. Do NOT use the main Gmail account password.
    *   Be mindful of Gmail's sending limits. Monitor for any issues.
*   **Input Validation:** Rigorous input validation on both frontend (for UX) and backend (Pydantic models in FastAPI).
*   **Credential Hashing:**
    *   Hash API tokens (e.g., SHA256) before storing in PostgreSQL and using as keys in Redis.
    *   Hash OTPs (e.g., SHA256) before storing in Redis.
*   **JWT Security:**
    *   Use a strong, unique secret key for signing JWTs (managed via environment variables).
    *   Set reasonable expiration times for JWTs.
    *   Transmit JWTs securely (e.g., in HttpOnly cookies or Authorization header).
*   **API Token Security:**
    *   Tokens should be high entropy.
    *   Displayed only once.
    *   Users educated on secure storage.
*   **Role-Based Access Control (RBAC):** Enforce roles using FastAPI dependencies based on JWT claims.
*   **CORS (Cross-Origin Resource Sharing):** Configure FastAPI's CORS middleware to allow requests only from the React frontend's origin.
*   **Common Web Vulnerabilities:** Address basics (XSS via React defaults, SQLi via ORM, CSRF if applicable).
*   **Secrets Management:** Store database credentials, JWT secrets, email App Password, Redis connection details, etc., using environment variables.
*   **Regular Updates:** `[POST-MVP]` for ongoing maintenance, but use up-to-date libraries for initial build.
*   **Extensive Security Hardening & Audits:** `[POST-MVP]`

---

## 7. Monitoring & Logging

*   **API Usage Logging:** `[MVP]`
    *   A FastAPI middleware will log basic details of requests to `/api/public/*` into the `api_usage_logs` table.
*   **Admin Dashboard:** `[MVP]` Will show basic logs as per frontend simplification.
*   **Application & System Monitoring:**
    *   `[MVP]` Standard Python logging for FastAPI to console/file.
    *   `[MVP]` Basic PostgreSQL logging.
    *   `[POST-MVP]` Prometheus, Grafana, centralized logging (ELK, Loki), `pgBadger`.

---

## 8. Deployment (Local Lab) `[MVP]`

*   **Containerization:** Docker for FastAPI, React (Nginx to serve static files), PostgreSQL, and Redis.
*   **Orchestration:** Docker Compose to define and run the multi-container application (FastAPI, Frontend/Nginx, PostgreSQL, Redis).
*   **Reverse Proxy:** Nginx with basic configuration for SSL termination and serving static files.
*   **Database:**
    *   PostgreSQL running in a Docker container.
    *   Redis running in a Docker container.
    *   **Backup Strategy:** `[MVP]` Document manual `pg_dump` steps for PostgreSQL. Redis data (OTPs, token cache) is generally transient or rebuildable from PostgreSQL if necessary, but persistence can be configured if needed. `[POST-MVP]` for automated backup scripts for PostgreSQL.
*   **Configuration:** Application settings (DB connection strings, JWT secrets, Gmail App Password, Redis connection URL) managed via environment variables passed to Docker containers.

---

## 9. Future Enhancements `[POST-MVP]`

*   Rate limits per API token.
*   More granular token scopes and permissions.
*   Webhook support for token activity (creation, revocation).
*   Admin ability to impersonate users (with strong audit logs).
*   More advanced analytics and reporting on API usage.
*   Periodic cleanup job for `auth_otp` table.
*   Automated database backups.
*   Advanced monitoring and alerting.
*   Full UI polish and advanced frontend features.
*   Comprehensive automated testing.

---
This combined design document, now focused on a 2-week MVP, should provide a solid and achievable foundation for developing your API Token Management Portal. 