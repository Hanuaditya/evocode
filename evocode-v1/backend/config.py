from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

class Settings(BaseSettings):
    # Existing settings
    GITHUB_TOKEN: str
    REPO_OWNER: str
    REPO_NAME: str
    REPO_PATH: str
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # Test settings
    TEST_TIMEOUT: int = 30
    TEST_AUTO_SETUP: bool = True
    TEST_SKIP_IF_MISSING: bool = False
    
    # Sandbox settings
    SANDBOX_ENABLE_TESTS: bool = True
    SANDBOX_CREATE_MINIMAL_TESTS: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
