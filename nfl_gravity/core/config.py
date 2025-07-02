"""Configuration management for NFL Gravity."""

import os
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class Config:
    """Configuration class for NFL Gravity application."""
    
    # API Keys
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    huggingface_api_key: Optional[str] = field(default_factory=lambda: os.getenv("HUGGINGFACE_API_KEY"))
    
    # LLM Configuration
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
    llm_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.3")))
    
    # Scraping Configuration
    request_delay_min: float = field(default_factory=lambda: float(os.getenv("REQUEST_DELAY_MIN", "1.0")))
    request_delay_max: float = field(default_factory=lambda: float(os.getenv("REQUEST_DELAY_MAX", "3.0")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30")))
    
    # Data Storage
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "data"))
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))
    output_formats: List[str] = field(default_factory=lambda: ["parquet", "csv"])
    
    # Team Configuration
    nfl_teams: List[str] = field(default_factory=lambda: [
        "49ers", "bears", "bengals", "bills", "broncos", "browns", "buccaneers",
        "cardinals", "chargers", "chiefs", "colts", "commanders", "cowboys",
        "dolphins", "eagles", "falcons", "giants", "jaguars", "jets", "lions",
        "packers", "panthers", "patriots", "raiders", "rams", "ravens",
        "saints", "seahawks", "steelers", "texans", "titans", "vikings"
    ])
    
    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # Feature Flags
    enable_social_media: bool = field(default_factory=lambda: os.getenv("ENABLE_SOCIAL_MEDIA", "true").lower() == "true")
    enable_wikipedia: bool = field(default_factory=lambda: os.getenv("ENABLE_WIKIPEDIA", "true").lower() == "true")
    enable_llm: bool = field(default_factory=lambda: os.getenv("ENABLE_LLM", "true").lower() == "true")
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of warnings/errors.
        
        Returns:
            List of validation messages
        """
        messages = []
        
        # Check LLM configuration
        if self.enable_llm:
            if self.llm_provider == "openai" and not self.openai_api_key:
                messages.append("OpenAI API key not found. LLM features will be disabled.")
            elif self.llm_provider == "huggingface" and not self.huggingface_api_key:
                messages.append("HuggingFace API key not found. LLM features will be disabled.")
        
        # Check directories
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            os.makedirs(self.log_dir, exist_ok=True)
        except PermissionError as e:
            messages.append(f"Cannot create directories: {e}")
        
        # Validate delay settings
        if self.request_delay_min >= self.request_delay_max:
            messages.append("request_delay_min should be less than request_delay_max")
        
        return messages
    
    def get_log_file(self) -> str:
        """Get the full path to the log file."""
        return os.path.join(self.log_dir, "nfl_gravity.log")
    
    def get_output_dir(self, timestamp: str) -> str:
        """Get the output directory for a specific timestamp."""
        return os.path.join(self.data_dir, timestamp)
