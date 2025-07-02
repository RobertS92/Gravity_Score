"""LLM adapter for various language model providers."""

import json
import logging
import os
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from ..core.exceptions import LLMError, AuthenticationError
from ..core.config import Config


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.llm.openai")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=config.openai_api_key)
        except ImportError:
            self.client = None
            self.logger.warning("OpenAI package not installed")
        except Exception as e:
            self.client = None
            self.logger.error(f"Error initializing OpenAI client: {e}")
    
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI."""
        if not self.client:
            raise LLMError("OpenAI client not available")
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.llm_temperature,
                response_format={"type": "json_object"} if kwargs.get('json_mode', True) else None,
                max_tokens=kwargs.get('max_tokens', 1000)
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise LLMError(f"OpenAI generation failed: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return (self.client is not None and 
                self.config.openai_api_key is not None and 
                len(self.config.openai_api_key.strip()) > 0)


class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace provider implementation (placeholder)."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.llm.huggingface")
        
        # Placeholder for HuggingFace implementation
        self.client = None
    
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using HuggingFace."""
        # Placeholder implementation
        raise LLMError("HuggingFace provider not yet implemented")
    
    def is_available(self) -> bool:
        """Check if HuggingFace is available."""
        return False


class LocalLLMProvider(BaseLLMProvider):
    """Local LLM provider (placeholder for future implementation)."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.llm.local")
        self.client = None
    
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using local LLM."""
        raise LLMError("Local LLM provider not yet implemented")
    
    def is_available(self) -> bool:
        """Check if local LLM is available."""
        return False


class LLMAdapter:
    """Main adapter class for LLM operations."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("nfl_gravity.llm")
        
        # Initialize providers
        self.providers = {
            'openai': OpenAIProvider(config),
            'huggingface': HuggingFaceProvider(config),
            'local': LocalLLMProvider(config)
        }
        
        # Select primary provider
        self.primary_provider = self._select_provider()
        
        if self.primary_provider:
            self.logger.info(f"LLM adapter initialized with provider: {self.primary_provider}")
        else:
            self.logger.warning("No LLM providers available - LLM features will be disabled")
    
    def _select_provider(self) -> Optional[str]:
        """Select the best available provider."""
        # Try configured provider first
        if self.config.llm_provider in self.providers:
            provider = self.providers[self.config.llm_provider]
            if provider.is_available():
                return self.config.llm_provider
        
        # Fallback to any available provider
        for name, provider in self.providers.items():
            if provider.is_available():
                return name
        
        return None
    
    def is_available(self) -> bool:
        """Check if any LLM provider is available."""
        return self.primary_provider is not None
    
    def extract_metrics(self, content: str, platform: str, custom_prompt: str = None) -> Dict[str, Any]:
        """
        Extract metrics from content using LLM.
        
        Args:
            content: Text content to analyze
            platform: Platform type (e.g., 'twitter', 'instagram', 'social_discovery')
            custom_prompt: Custom prompt to use instead of default
            
        Returns:
            Dictionary with extracted metrics
        """
        if not self.is_available():
            self.logger.warning("No LLM provider available for metric extraction")
            return {}
        
        try:
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = self._build_extraction_prompt(content, platform)
            
            provider = self.providers[self.primary_provider]
            response = provider.generate_response(prompt, json_mode=True)
            
            # Parse JSON response
            try:
                result = json.loads(response)
                self.logger.debug(f"Successfully extracted metrics for {platform}")
                return result
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM response as JSON: {e}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error extracting metrics with LLM: {e}")
            return {}
    
    def _build_extraction_prompt(self, content: str, platform: str) -> str:
        """Build extraction prompt based on platform."""
        base_prompt = f"""
        Analyze the following content and extract relevant metrics and information.
        Return the results as a JSON object.
        
        Content: {content[:2000]}  # Limit content length
        
        Platform: {platform}
        """
        
        if platform == 'twitter':
            return base_prompt + """
            Extract:
            - follower_count: number of followers (convert K/M notation to numbers)
            - following_count: number of following
            - tweet_count: number of tweets
            - verified: boolean if account is verified
            - bio: account bio/description
            - location: user location if available
            
            Return JSON format:
            {
                "follower_count": 0,
                "following_count": 0,
                "tweet_count": 0,
                "verified": false,
                "bio": "",
                "location": ""
            }
            """
        
        elif platform == 'instagram':
            return base_prompt + """
            Extract:
            - follower_count: number of followers (convert K/M notation to numbers)
            - following_count: number of following
            - post_count: number of posts
            - verified: boolean if account is verified
            - bio: account bio/description
            - avg_likes: average likes per post if visible
            
            Return JSON format:
            {
                "follower_count": 0,
                "following_count": 0,
                "post_count": 0,
                "verified": false,
                "bio": "",
                "avg_likes": 0
            }
            """
        
        elif platform == 'social_discovery':
            return base_prompt + """
            Extract social media handles mentioned in the content:
            - twitter_handle: Twitter/X username without @ symbol
            - instagram_handle: Instagram username without @ symbol
            - facebook_handle: Facebook username if found
            - confidence: confidence score 0-1 for the extraction
            
            Only extract handles that clearly belong to NFL players mentioned in the content.
            
            Return JSON format:
            {
                "twitter_handle": "",
                "instagram_handle": "",
                "facebook_handle": "",
                "confidence": 0.0
            }
            """
        
        else:
            return base_prompt + """
            Extract any relevant metrics, statistics, or structured information from the content.
            Return as JSON with appropriate field names and values.
            """
    
    def enhance_player_data(self, player_data: Dict[str, Any], content: str) -> Dict[str, Any]:
        """
        Enhance player data using LLM analysis of content.
        
        Args:
            player_data: Existing player data
            content: Additional content to analyze
            
        Returns:
            Enhanced player data dictionary
        """
        if not self.is_available():
            return player_data
        
        try:
            prompt = f"""
            Analyze the following content about an NFL player and extract additional information
            to enhance the existing player data. Return only new/additional information as JSON.
            
            Existing player data: {json.dumps(player_data, default=str)[:1000]}
            
            Additional content: {content[:2000]}
            
            Extract any missing information such as:
            - Career highlights and achievements
            - Awards and honors
            - College statistics or information
            - Draft information
            - Notable career moments
            - Personal information (hometown, family, etc.)
            
            Return JSON with only new information found in the content.
            Do not repeat information already in the existing data.
            """
            
            provider = self.providers[self.primary_provider]
            response = provider.generate_response(prompt, json_mode=True)
            
            try:
                enhancements = json.loads(response)
                # Merge enhancements with existing data
                enhanced_data = player_data.copy()
                enhanced_data.update(enhancements)
                
                self.logger.debug("Successfully enhanced player data with LLM")
                return enhanced_data
                
            except json.JSONDecodeError:
                self.logger.error("Failed to parse LLM enhancement response")
                return player_data
                
        except Exception as e:
            self.logger.error(f"Error enhancing player data with LLM: {e}")
            return player_data
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text content.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        if not self.is_available():
            return {'sentiment': 'neutral', 'confidence': 0.0}
        
        try:
            prompt = f"""
            Analyze the sentiment of the following text and provide a rating and confidence score.
            
            Text: {text[:1000]}
            
            Return JSON format:
            {{
                "sentiment": "positive|negative|neutral",
                "score": 0.0,
                "confidence": 0.0
            }}
            
            Where:
            - sentiment: overall sentiment classification
            - score: sentiment score from -1 (most negative) to 1 (most positive)
            - confidence: confidence in the analysis from 0 to 1
            """
            
            provider = self.providers[self.primary_provider]
            response = provider.generate_response(prompt, json_mode=True)
            
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                return {'sentiment': 'neutral', 'confidence': 0.0}
                
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return {'sentiment': 'neutral', 'confidence': 0.0}
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about available providers."""
        return {
            'primary_provider': self.primary_provider,
            'available_providers': [name for name, provider in self.providers.items() 
                                  if provider.is_available()],
            'provider_status': {name: provider.is_available() 
                              for name, provider in self.providers.items()}
        }
