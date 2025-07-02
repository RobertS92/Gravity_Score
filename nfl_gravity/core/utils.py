"""Utility functions for NFL Gravity package."""

import os
import re
import logging
import random
import time
from typing import Optional, List
from urllib.robotparser import RobotFileParser
from datetime import datetime


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration for NFL Gravity.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("nfl_gravity")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_user_agent() -> str:
    """
    Get a random user agent string for web scraping.
    
    Returns:
        Random user agent string
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]
    return random.choice(user_agents)


def clean_text(text: str) -> str:
    """
    Clean and normalize text data.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove special characters that might cause issues
    text = re.sub(r'[^\w\s\-.,!?()\'\"@#$%&*+/=<>:;]', '', text)
    
    return text


def check_robots_txt(url: str, user_agent: str = '*') -> bool:
    """
    Check if scraping is allowed by robots.txt.
    
    Args:
        url: URL to check
        user_agent: User agent string
        
    Returns:
        True if scraping is allowed, False otherwise
    """
    try:
        from urllib.parse import urljoin, urlparse
        
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        robots_url = urljoin(base_url, '/robots.txt')
        
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If we can't check robots.txt, assume it's allowed
        return True


def polite_delay(min_delay: float = 1.0, max_delay: float = 3.0) -> None:
    """
    Add a polite delay between requests.
    
    Args:
        min_delay: Minimum delay in seconds
        max_delay: Maximum delay in seconds
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def extract_social_metrics(text: str) -> dict:
    """
    Extract social media metrics from text using regex patterns.
    
    Args:
        text: Text containing potential social metrics
        
    Returns:
        Dictionary of extracted metrics
    """
    metrics = {}
    
    # Twitter/X followers pattern
    twitter_pattern = r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:K|M)?\s*(?:followers?|following)'
    twitter_matches = re.findall(twitter_pattern, text, re.IGNORECASE)
    if twitter_matches:
        metrics['twitter_followers'] = convert_metric_to_number(twitter_matches[0])
    
    # Instagram followers pattern
    instagram_pattern = r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:K|M)?\s*(?:followers?|following)'
    instagram_matches = re.findall(instagram_pattern, text, re.IGNORECASE)
    if instagram_matches:
        metrics['instagram_followers'] = convert_metric_to_number(instagram_matches[0])
    
    # Engagement metrics
    likes_pattern = r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:K|M)?\s*likes?'
    likes_matches = re.findall(likes_pattern, text, re.IGNORECASE)
    if likes_matches:
        metrics['avg_likes'] = convert_metric_to_number(likes_matches[0])
    
    return metrics


def convert_metric_to_number(metric_str: str) -> int:
    """
    Convert metric string (e.g., '1.2K', '5M') to number.
    
    Args:
        metric_str: Metric string to convert
        
    Returns:
        Numeric value
    """
    metric_str = metric_str.replace(',', '').strip()
    
    if 'K' in metric_str:
        return int(float(metric_str.replace('K', '')) * 1000)
    elif 'M' in metric_str:
        return int(float(metric_str.replace('M', '')) * 1000000)
    else:
        return int(float(metric_str))


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp string
    """
    return datetime.now().isoformat()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem usage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized.strip('_')


def create_output_directory(base_dir: str) -> str:
    """
    Create timestamped output directory.
    
    Args:
        base_dir: Base directory path
        
    Returns:
        Created directory path
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    output_dir = os.path.join(base_dir, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir
