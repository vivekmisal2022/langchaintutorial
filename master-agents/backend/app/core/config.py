"""Application configuration using Pydantic Settings."""
from __future__ import annotations

import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server Configuration
    port: int = 8000
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # Service Mode Selection
    mock_mode: bool = True
    agentic_mode: bool = False  # Enable DeepAgent with MCP tools

    # MCP Server
    mcp_server_url: str = "http://localhost:3001/mcp"  # For Kyma: http://backend-mcp-service:3001/mcp
    
    # SAP Generative AI Hub
    aicore_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("AICORE_BASE_URL", "AICC_BASE_URL"),
    )
    aicore_auth_url: str = Field(
        default="",
        validation_alias=AliasChoices("AICORE_AUTH_URL", "AICC_AUTH_URL"),
    )
    aicore_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("AICORE_CLIENT_ID", "AICC_CLIENT_ID"),
    )
    aicore_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("AICORE_CLIENT_SECRET", "AICC_CLIENT_SECRET"),
    )
    aicore_resource_group: str = Field(
        default="default",
        validation_alias=AliasChoices("AICORE_RESOURCE_GROUP", "AICC_RESOURCE_GROUP"),
    )
    
    # SAP Generative AI Hub (US region for audio models)
    aicore_base_url_us: str = ""
    aicore_auth_url_us: str = ""
    aicore_client_id_us: str = ""
    aicore_client_secret_us: str = ""
    aicore_resource_group_us: str = ""
    
    # LLM Models
    llm_model: str = "gpt-4.1"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1000
    
    summarization_llm_model: str = "gpt-5-mini"  # Faster/cheaper model for title generation
    summarization_temperature: float = 0.3
    summarization_max_tokens: int = 50
    
    # Audio Transcription
    audio_transcription_model: str = "gemini-2.5-flash"
    audio_model_instance: str = "US"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    def ensure_sdk_env(self) -> None:
        """Ensure required SAP AI Core env vars are exported for the SDK."""
        env_map = {
            "AICORE_BASE_URL": self.aicore_base_url,
            "AICORE_AUTH_URL": self.aicore_auth_url,
            "AICORE_CLIENT_ID": self.aicore_client_id,
            "AICORE_CLIENT_SECRET": self.aicore_client_secret,
            "AICORE_RESOURCE_GROUP": self.aicore_resource_group,
            # Backwards compatibility aliases
            "AICC_BASE_URL": self.aicore_base_url,
            "AICC_AUTH_URL": self.aicore_auth_url,
            "AICC_CLIENT_ID": self.aicore_client_id,
            "AICC_CLIENT_SECRET": self.aicore_client_secret,
            "AICC_RESOURCE_GROUP": self.aicore_resource_group,
        }

        for key, value in env_map.items():
            if value:
                os.environ[key] = value


# Global settings instance
settings = Settings()
settings.ensure_sdk_env()
