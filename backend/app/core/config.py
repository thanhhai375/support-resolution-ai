from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # JWT
    jwt_secret_key: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Server (matches the /api proxy target in frontend/vite.config.ts)
    host: str = "0.0.0.0"
    port: int = 8080

    # Allowed frontend origins for CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Allowed user roles for RBAC checks
    valid_roles: list[str] = ["user", "agent", "admin"]

    # Default admin account seeded on startup
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "Admin@123"


settings = Settings()
