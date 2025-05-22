# Initial Setup Checklist (2-Week MVP)

## I. General Project Setup & Configuration (Day 1)

- [x] Initialize Git repository.
- [x] Create main project directories (`backend`, `frontend`, `docs`, `checklists`, `deployment/docker`).
- [x] Define basic `README.md` for the project.
- [x] Set up environment variable management (e.g., `.env` files for local development, ensure `.env` is in `.gitignore`).
    - [x] Define variables for: Database connection, JWT Secret, Gmail App Password, Frontend URL (for CORS), Redis Connection URL.

## II. Backend (FastAPI) - Core MVP (Days 1-7)

### A. Core Setup & Structure
- [x] Initialize FastAPI project (`app/main.py`).
- [x] Implement project structure as per design (api, core, db, services).
    - [x] Add `services/redis_service.py` for Redis client and utilities.
- [x] Configure basic logging (to console/file).
- [x] Setup Redis client connection.
- [x] Setup Pydantic models (`schemas.py`) for:
    - [x] User (UserCreate, UserRead)
    - [x] OTP (OtpRequest, OtpVerify) - (Interaction with these will change to Redis)
    - [x] Token (TokenCreate, TokenRead - for user, TokenAdminRead - for admin view)
- [x] Setup database connection and async session management (`db/session.py`, `db/base.py`).

### B. Database Models & CRUD (`db/models.py`, `db/crud.py`)
- [x] Implement `User` SQLAlchemy model.
- [x] Implement `AuthOtp` SQLAlchemy model.
    - [x] This model will be **removed**. CRUD operations for OTP will use Redis.
- [x] Implement `ApiToken` SQLAlchemy model.
    - [x] CRUD operations for `ApiToken` will be updated:
        - [x] Creation: Store in PostgreSQL and cache in Redis.
        - [x] Validation lookup: Prioritize Redis.
        - [ ] Revocation: Update in PostgreSQL and Redis.
- [x] Implement `ApiUsageLog` SQLAlchemy model.
- [x] Implement basic async CRUD functions for User (create, get by email, get by ID).
- [x] Implement basic async CRUD functions for AuthOtp (create, get by email, mark as used).
    - [x] These CRUD functions will be **rewritten** to use Redis (e.g., in `services/otp_service.py`).
- [x] Implement basic async CRUD functions for ApiToken (create, get by user_id, get by ID, get by hashed_token, list all for admin, revoke).
    - [x] `create`: Update to write to PostgreSQL and cache in Redis.
    - [x] `get_by_hashed_token`: Update to query Redis first for validation purposes.
    - [ ] `revoke`: Update to modify PostgreSQL and Redis.
- [x] Implement basic async CRUD functions for ApiUsageLog (create log entry).

### C. Authentication (`api/v1/endpoints/auth.py`, `services/otp_service.py`, `services/email_service.py`)
- [x] Implement `POST /auth/request-otp` endpoint:
    - [x] Generate 5-digit OTP.
    - [x] Hash OTP (SHA256).
    - [x] Store `user_email`, `otp_hash`, `expires_at` in `auth_otp` table.
        - [x] This will change to: Store OTP data in Redis with expiry.
    - [x] Send plain OTP email using Gmail (via `smtp.gmail.com` with App Password).
- [x] Implement `POST /auth/verify-otp` endpoint:
    - [x] Verify OTP hash, expiry, and used status.
        - [x] This will change to: Verify OTP against data in Redis (hash, implicit expiry, delete on use).
    - [x] Mark OTP as used.
        - [x] This will change to: Delete OTP from Redis on successful verification.
    - [x] Generate JWT token (containing user_id, email, role, exp).
- [x] Implement JWT utility functions (create token, verify token - `core/security.py`).
- [x] Implement dependency to get current active user from JWT (`core/dependencies.py`).

### D. User API Token Management (`api/v1/endpoints/tokens.py`)
- [x] Implement `POST /tokens` (protected, user role):
    - [x] Generate secure API token string.
    - [x] Hash API token (SHA256).
    - [x] Store token metadata (user_id, name, hashed_token, expires_at, etc.).
        - [x] This will change to: Store in PostgreSQL `api_tokens` table and cache necessary validation data in Redis.
    - [x] Return plain API token **once** to the user.
- [x] Implement `GET /tokens` (protected, user role): List tokens for the authenticated user (metadata only).
    - [ ] (No change, still queries PostgreSQL `api_tokens` table).
- [x] Implement `DELETE /tokens/{token_id}` (protected, user role): Revoke an API token.
    - [ ] This will change to: Update revoked status in PostgreSQL `api_tokens` table and update/delete entry in Redis.

### E. Public API Validation (`api/v1/endpoints/public_api_proxy.py` or Middleware)
- [x] Implement middleware for `/api/public/*` routes.
- [x] Extract API token from header (`X-API-Key` or `Authorization: Bearer`).
- [x] Validate token: hash comparison, check expiry, check revoked status.
    - [x] This will change to: Query Redis first for token validity (existence, expiry, revoked status). PostgreSQL is fallback/source of truth if needed, but Redis is primary for speed.
- [x] Log API usage to `api_usage_logs` table (basic details: token_id (if valid), user_id, path, method, status, timestamp).
- [x] If valid, allow request to proceed (for MVP, this might just return a success message or proxy to a dummy endpoint if no actual public APIs are ready).

### F. User Profile (`api/v1/endpoints/users.py` - Simplified for MVP)
- [x] Implement `GET /users/me` (protected, user role): Get current authenticated user's details (email, role).

### G. Admin APIs (`api/v1/endpoints/admin.py` - Basic MVP)
- [x] Implement dependency for `get_current_active_admin` (`core/dependencies.py`).
- [x] Implement `GET /admin/users` (protected, admin role): List all users (email, role).
- [x] Implement `GET /admin/tokens` (protected, admin role): List all API tokens (metadata: name, user_email, created/expiry, revoked status).
- [x] Implement `GET /admin/usage/logs` (protected, admin role): List raw API usage logs (paginated if possible).

### H. Core Security & Config
- [x] Implement hashing for API tokens and OTPs (`core/security.py`).
- [x] Configure CORS middleware (`main.py`) to allow frontend origin.
- [x] Load sensitive configurations (DB URL, JWT Secret, Gmail App Password) from environment variables (`core/config.py`).
    - [x] Add Redis Connection URL to environment variables.

## III. Database (PostgreSQL) - MVP (Concurrent with Backend)

- [x] Setup PostgreSQL instance (e.g., via Docker).
- [x] Create database user and database for the application.
- [x] Apply initial schema (run CREATE TABLE statements or use Alembic/SQLAlchemy migrations for first setup).
    - [x] `users` table.
    - [x] `auth_otp` table.
        - [x] This table will be **removed** from PostgreSQL schema.
    - [x] `api_tokens` table.
        - [x] Schema remains, role as primary store for metadata confirmed. Redis caches some of this data.
    - [x] `api_usage_logs` table.
- [x] Ensure asynchronous connection from FastAPI is working.

## IV. Frontend (React) - Core MVP (Days 3-10)

### A. Project Setup & Basic Theming
- [ ] Initialize React project (e.g., using Vite or Create React App).
- [ ] Setup basic folder structure (`pages`, `components`, `services`, `hooks`, `contexts`, `assets`).
- [ ] Implement basic "Black on Silver" theme (CSS Custom Properties for colors, Inter font).
    - [ ] Global styles for background, text colors, default font.
- [ ] Setup React Router (`react-router-dom`).
- [ ] Configure Axios or `fetch` wrapper for API calls.
- [ ] Setup React Query or SWR for server state management.
- [ ] Setup basic Context for Auth State (user, token, isAuthenticated).

### B. Authentication Pages
- [ ] Create `LoginPage`:
    - [ ] Email input field.
    - [ ] Call `POST /auth/request-otp`.
    - [ ] Handle loading/error states.
    - [ ] Redirect to OTP page on success.
- [ ] Create `OtpVerificationPage`:
    - [ ] OTP input field.
    - [ ] Call `POST /auth/verify-otp`.
    - [ ] Store JWT and user info (in context/localStorage) on success.
    - [ ] Handle loading/error states.
    - [ ] Redirect to dashboard on successful login.
- [ ] Implement `AuthGuard` / `ProtectedRoute` HOC or component for routes requiring authentication.
- [ ] Implement `AdminGuard` / `ProtectedAdminRoute` for admin-only routes.

### C. User Dashboard & Token Management
- [ ] Create `UserDashboardPage` (or a layout with nested routes).
- [ ] Create `ApiTokensListPage` component:
    - [ ] Fetch and display user's API tokens (masked token, name, expiry, status) from `GET /tokens`.
    - [ ] Button to trigger "Create New Token" modal/view.
    - [ ] Action to revoke a token (call `DELETE /tokens/{token_id}`).
- [ ] Create `CreateTokenModal` (or page component):
    - [ ] Input for token name (optional).
    *   Input for expiration date (optional, simple date input for MVP).
    *   Call `POST /tokens`.
    *   Display the generated API token **ONCE** with clear instructions to copy.

### D. Basic Admin Panel
- [ ] Create basic `AdminLayout`.
- [ ] Create `AdminUsersPage`:
    - [ ] Fetch and display list of users (email, role) from `GET /admin/users` in a simple table.
- [ ] Create `AdminTokensPage`:
    - [ ] Fetch and display list of all API tokens (metadata) from `GET /admin/tokens` in a simple table.
- [ ] Create `AdminUsageLogsPage`:
    - [ ] Fetch and display raw API usage logs from `GET /admin/usage/logs` in a simple, paginated table.

### E. General Frontend
- [ ] Basic responsive layout for key pages.
- [ ] Consistent error handling and display of messages from API.
- [ ] Logout functionality (clear token, redirect to login).

## V. Deployment (Docker & Nginx) - MVP (Days 8-10)

- [ ] Create `Dockerfile` for FastAPI backend.
- [ ] Create `Dockerfile` for React frontend (multi-stage build, serve with Nginx).
- [ ] Create basic Nginx configuration (`nginx.conf`) to:
    - [ ] Serve React static files.
    - [ ] Reverse proxy API requests to the FastAPI backend (e.g., `/api/*` -> `fastapi_app:8000`).
    - [ ] Basic SSL setup (self-signed for local lab initially, if HTTPS is needed immediately).
- [ ] Create `docker-compose.yml` to orchestrate:
    - [ ] FastAPI service.
    - [ ] Frontend (Nginx) service.
    - [ ] PostgreSQL service (with volume for data persistence).
    - [ ] Add Redis service.
- [ ] Test local deployment using `docker-compose up`.
- [ ] Document manual `pg_dump` steps for database backup.
    - [ ] Add note on Redis data (transient/cache or persistence options).

## VI. Final MVP Review & Testing (End of Week 2)

- [ ] Test all core user flows (Login, OTP, Token Create/List/Revoke).
- [ ] Test all core admin views (User list, Token list, Usage log list).
- [ ] Test public API endpoint access with a valid and invalid token.
- [ ] Basic cross-browser check (if applicable to lab environment).
- [ ] Quick security check of configurations (secrets not exposed, basic auth working).
- [ ] Ensure all `[MVP]` tasks in this checklist are addressed.
