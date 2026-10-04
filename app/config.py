from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "observable-agent"
    env: str = "development"
    log_level: str = "INFO"
    
    # LLM configuration
    llm_provider: str = "mock"  # "mock", "openai", "gemini"
    llm_model: str = "mock-gpt-4o"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    
    # OpenTelemetry configuration
    otel_service_name: str = "observable-agent"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_exporter_otlp_protocol: str = "grpc"
    enable_console_exporter: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
