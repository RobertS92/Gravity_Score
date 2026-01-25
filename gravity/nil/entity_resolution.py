"""
Entity Resolution Service
Deterministic and probabilistic matching to assign events to canonical athlete_id
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime
import uuid
from difflib import SequenceMatcher
import re

from gravity.storage import get_storage_manager
from gravity.db.models import Athlete, AthleteEvent, EntityMatch

logger = logging.getLogger(__name__)


class EntityResolver:
    """
    Resolves athlete entities using deterministic and probabilistic matching
    
    Matching Rules (in order of priority):
    1. Deterministic: Verified social handle + name match
    2. Deterministic: Team + Jersey + Season + Name match
    3. Probabilistic: Name similarity + attribute overlap
    4. Queue for review if confidence < threshold
    """
    
    # Configuration
    REVIEW_THRESHOLD = 0.85  # Confidence threshold for automatic matching
    NAME_SIMILARITY_WEIGHT = 0.40
    ATTRIBUTE_OVERLAP_WEIGHT = 0.30
    SCHOOL_MATCH_WEIGHT = 0.15
    SPORT_MATCH_WEIGHT = 0.10
    POSITION_MATCH_WEIGHT = 0.05
    
    def __init__(self):
        """Initialize entity resolver"""
        self.storage = get_storage_manager()
        logger.info("Entity resolver initialized")
    
    # ========================================================================
    # MAIN RESOLUTION METHODS
    # ========================================================================
    
    def resolve_athlete(
        self,
        name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        position: Optional[str] = None,
        jersey_number: Optional[int] = None,
        season_id: Optional[str] = None,
        social_handles: Optional[Dict[str, str]] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[uuid.UUID], float, str]:
        """
        Resolve athlete to canonical athlete_id
        
        Args:
            name: Athlete name
            school: School/college name
            sport: Sport type
            position: Position
            jersey_number: Jersey number
            season_id: Season identifier
            social_handles: Dict of platform -> handle
            attributes: Additional attributes for matching
        
        Returns:
            Tuple of (athlete_id, confidence, explanation)
        """
        logger.debug(f"Resolving athlete: {name} ({school}, {sport})")
        
        # Try deterministic matching first
        athlete_id, explanation = self._match_deterministic(
            name, school, sport, position, jersey_number, season_id, social_handles
        )
        
        if athlete_id:
            logger.info(f"Deterministic match: {name} -> {athlete_id}")
            return athlete_id, 1.0, explanation
        
        # Try probabilistic matching
        matches = self._match_probabilistic(
            name, school, sport, position, attributes
        )
        
        if matches:
            # Get best match
            best_match = matches[0]
            confidence = best_match['confidence']
            athlete_id = best_match['athlete_id']
            explanation = best_match['explanation']
            
            if confidence >= self.REVIEW_THRESHOLD:
                logger.info(f"Probabilistic match: {name} -> {athlete_id} (confidence: {confidence:.2f})")
                return athlete_id, confidence, explanation
            else:
                logger.info(f"Low confidence match for {name}: {confidence:.2f} - queuing for review")
                return athlete_id, confidence, explanation + " [NEEDS REVIEW]"
        
        # No match found
        logger.debug(f"No match found for athlete: {name}")
        return None, 0.0, "No matching athlete found"
    
    def create_or_resolve_athlete(
        self,
        name: str,
        school: Optional[str] = None,
        sport: Optional[str] = None,
        **attributes
    ) -> Tuple[uuid.UUID, bool, float]:
        """
        Resolve existing athlete or create new one
        
        Args:
            name: Athlete name
            school: School name
            sport: Sport type
            **attributes: Additional attributes
        
        Returns:
            Tuple of (athlete_id, is_new, confidence)
        """
        # Try to resolve
        athlete_id, confidence, explanation = self.resolve_athlete(
            name, school, sport, **attributes
        )
        
        if athlete_id:
            return athlete_id, False, confidence
        
        # Create new athlete
        athlete_id = self._create_athlete(name, school, sport, **attributes)
        logger.info(f"Created new athlete: {name} -> {athlete_id}")
        
        return athlete_id, True, 1.0
    
    # ========================================================================
    # DETERMINISTIC MATCHING
    # ========================================================================
    
    def _match_deterministic(
        self,
        name: str,
        school: Optional[str],
        sport: Optional[str],
        position: Optional[str],
        jersey_number: Optional[int],
        season_id: Optional[str],
        social_handles: Optional[Dict[str, str]]
    ) -> Tuple[Optional[uuid.UUID], str]:
        """
        Deterministic matching using high-confidence rules
        
        Returns:
            Tuple of (athlete_id, explanation)
        """
        with self.storage.get_session() as session:
            # Rule 1: Verified social handle match
            if social_handles:
                athlete = self._match_by_social_handle(session, name, social_handles)
                if athlete:
                    return athlete.athlete_id, f"Verified social handle match: {list(social_handles.keys())[0]}"
            
            # Rule 2: Team + Jersey + Season + Name match
            if school and jersey_number and season_id:
                athlete = self._match_by_jersey(session, name, school, jersey_number, season_id)
                if athlete:
                    return athlete.athlete_id, f"Roster match: {school} #{jersey_number} ({season_id})"
            
            # Rule 3: Exact name + school + sport match (if unique)
            if school and sport:
                athletes = session.query(Athlete).filter(
                    Athlete.canonical_name.ilike(name),
                    Athlete.school.ilike(school),
                    Athlete.sport.ilike(sport),
                    Athlete.is_active == True
                ).all()
                
                if len(athletes) == 1:
                    return athletes[0].athlete_id, f"Unique exact match: {name} at {school} ({sport})"
        
        return None, ""
    
    def _match_by_social_handle(
        self,
        session,
        name: str,
        social_handles: Dict[str, str]
    ) -> Optional[Athlete]:
        """Match by verified social media handle"""
        # This would require storing social handles in athlete metadata
        # For now, we'll return None and implement this later when we have social data
        # TODO: Implement social handle matching when metadata is populated
        return None
    
    def _match_by_jersey(
        self,
        session,
        name: str,
        school: str,
        jersey_number: int,
        season_id: str
    ) -> Optional[Athlete]:
        """Match by team roster (jersey number + season)"""
        # Match by jersey + school + season
        athletes = session.query(Athlete).filter(
            Athlete.school.ilike(school),
            Athlete.jersey_number == jersey_number,
            Athlete.season_id == season_id
        ).all()
        
        # Check name similarity
        for athlete in athletes:
            similarity = self._calculate_name_similarity(name, athlete.canonical_name)
            if similarity > 0.8:
                return athlete
        
        return None
    
    # ========================================================================
    # PROBABILISTIC MATCHING
    # ========================================================================
    
    def _match_probabilistic(
        self,
        name: str,
        school: Optional[str],
        sport: Optional[str],
        position: Optional[str],
        attributes: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Probabilistic matching using similarity scoring
        
        Returns:
            List of potential matches sorted by confidence (descending)
        """
        matches = []
        
        with self.storage.get_session() as session:
            # Get candidate athletes (same sport, similar name, or same school)
            candidates = self._get_candidate_athletes(session, name, school, sport)
            
            if not candidates:
                return []
            
            # Score each candidate
            for candidate in candidates:
                score, explanation = self._calculate_match_score(
                    name, school, sport, position, attributes, candidate
                )
                
                if score > 0.3:  # Minimum threshold for consideration
                    matches.append({
                        'athlete_id': candidate.athlete_id,
                        'confidence': score,
                        'explanation': explanation,
                        'candidate_name': candidate.canonical_name,
                        'candidate_school': candidate.school
                    })
        
        # Sort by confidence (descending)
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        return matches
    
    def _get_candidate_athletes(
        self,
        session,
        name: str,
        school: Optional[str],
        sport: Optional[str]
    ) -> List[Athlete]:
        """Get candidate athletes for probabilistic matching"""
        # Start with base query
        query = session.query(Athlete).filter(Athlete.is_active == True)
        
        # Filter by sport if provided
        if sport:
            query = query.filter(Athlete.sport.ilike(sport))
        
        # Filter by school if provided (or similar school names)
        if school:
            query = query.filter(Athlete.school.ilike(f"%{school}%"))
        
        # Get candidates
        candidates = query.limit(50).all()  # Limit to avoid too many comparisons
        
        # Also search by name similarity if we don't have many candidates
        if len(candidates) < 10:
            # Extract first/last name
            name_parts = name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = name_parts[-1]
                
                additional = session.query(Athlete).filter(
                    Athlete.is_active == True,
                    Athlete.canonical_name.ilike(f"%{first_name}%{last_name}%")
                ).limit(20).all()
                
                # Merge (avoiding duplicates)
                candidate_ids = {c.athlete_id for c in candidates}
                for athlete in additional:
                    if athlete.athlete_id not in candidate_ids:
                        candidates.append(athlete)
        
        return candidates
    
    def _calculate_match_score(
        self,
        name: str,
        school: Optional[str],
        sport: Optional[str],
        position: Optional[str],
        attributes: Optional[Dict[str, Any]],
        candidate: Athlete
    ) -> Tuple[float, str]:
        """
        Calculate probabilistic match score
        
        Returns:
            Tuple of (score, explanation)
        """
        score = 0.0
        explanation_parts = []
        
        # Name similarity (40% weight)
        name_sim = self._calculate_name_similarity(name, candidate.canonical_name)
        name_contribution = name_sim * self.NAME_SIMILARITY_WEIGHT
        score += name_contribution
        explanation_parts.append(f"Name similarity: {name_sim:.2f}")
        
        # School match (15% weight)
        if school and candidate.school:
            if school.lower() == candidate.school.lower():
                score += self.SCHOOL_MATCH_WEIGHT
                explanation_parts.append("School: exact match")
            elif self._schools_similar(school, candidate.school):
                score += self.SCHOOL_MATCH_WEIGHT * 0.7
                explanation_parts.append("School: similar")
        
        # Sport match (10% weight)
        if sport and candidate.sport:
            if sport.lower() == candidate.sport.lower():
                score += self.SPORT_MATCH_WEIGHT
                explanation_parts.append("Sport: match")
        
        # Position match (5% weight)
        if position and candidate.position:
            if self._positions_similar(position, candidate.position):
                score += self.POSITION_MATCH_WEIGHT
                explanation_parts.append("Position: match")
        
        # Attribute overlap (30% weight)
        if attributes:
            attr_score = self._calculate_attribute_overlap(attributes, candidate)
            score += attr_score * self.ATTRIBUTE_OVERLAP_WEIGHT
            if attr_score > 0:
                explanation_parts.append(f"Attributes: {attr_score:.2f} overlap")
        
        explanation = " | ".join(explanation_parts)
        
        return min(1.0, score), explanation
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity using multiple methods"""
        if not name1 or not name2:
            return 0.0
        
        # Normalize names
        name1 = self._normalize_name(name1)
        name2 = self._normalize_name(name2)
        
        # Exact match
        if name1 == name2:
            return 1.0
        
        # Sequence matcher (overall similarity)
        seq_sim = SequenceMatcher(None, name1, name2).ratio()
        
        # Check first/last name match
        parts1 = name1.split()
        parts2 = name2.split()
        
        if len(parts1) >= 2 and len(parts2) >= 2:
            first_match = parts1[0] == parts2[0]
            last_match = parts1[-1] == parts2[-1]
            
            if first_match and last_match:
                return 0.95  # Very high confidence for first+last match
            elif first_match or last_match:
                return max(seq_sim, 0.7)  # Boost if one name matches
        
        return seq_sim
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        # Remove special characters, extra spaces
        name = re.sub(r'[^\w\s]', '', name.lower())
        name = ' '.join(name.split())
        return name
    
    def _schools_similar(self, school1: str, school2: str) -> bool:
        """Check if two school names are similar"""
        s1 = school1.lower()
        s2 = school2.lower()
        
        # Check for common abbreviations
        abbrev_map = {
            'university': 'univ',
            'college': 'coll',
            'state': 'st',
            'tech': 'technology'
        }
        
        for full, abbrev in abbrev_map.items():
            s1 = s1.replace(full, abbrev)
            s2 = s2.replace(full, abbrev)
        
        # Check if one contains the other
        if s1 in s2 or s2 in s1:
            return True
        
        # Check similarity
        return SequenceMatcher(None, s1, s2).ratio() > 0.8
    
    def _positions_similar(self, pos1: str, pos2: str) -> bool:
        """Check if positions are similar"""
        p1 = pos1.lower().strip()
        p2 = pos2.lower().strip()
        
        if p1 == p2:
            return True
        
        # Position groups (positions in same group are similar)
        position_groups = [
            ['qb', 'quarterback'],
            ['rb', 'running back', 'running-back', 'runningback'],
            ['wr', 'wide receiver', 'wide-receiver', 'receiver'],
            ['te', 'tight end', 'tight-end'],
            ['ol', 'offensive line', 'offensive-line', 'o-line'],
            ['dl', 'defensive line', 'defensive-line', 'd-line'],
            ['lb', 'linebacker', 'line-backer'],
            ['db', 'defensive back', 'defensive-back', 'secondary'],
            ['cb', 'cornerback', 'corner-back'],
            ['s', 'safety']
        ]
        
        for group in position_groups:
            if p1 in group and p2 in group:
                return True
        
        return False
    
    def _calculate_attribute_overlap(self, attributes: Dict[str, Any], candidate: Athlete) -> float:
        """Calculate overlap in additional attributes"""
        if not attributes:
            return 0.0
        
        matches = 0
        total = 0
        
        # Check metadata fields
        candidate_metadata = candidate.metadata or {}
        
        for key, value in attributes.items():
            if value is None:
                continue
            
            total += 1
            
            # Check if attribute matches
            if key in candidate_metadata:
                if str(candidate_metadata[key]).lower() == str(value).lower():
                    matches += 1
        
        return matches / total if total > 0 else 0.0
    
    # ========================================================================
    # ATHLETE CREATION
    # ========================================================================
    
    def _create_athlete(
        self,
        name: str,
        school: Optional[str],
        sport: Optional[str],
        **attributes
    ) -> uuid.UUID:
        """Create new athlete record"""
        with self.storage.get_session() as session:
            athlete = Athlete(
                canonical_name=name,
                school=school,
                sport=sport,
                position=attributes.get('position'),
                conference=attributes.get('conference'),
                jersey_number=attributes.get('jersey_number'),
                class_year=attributes.get('class_year'),
                season_id=attributes.get('season_id'),
                is_active=True,
                metadata=attributes
            )
            
            session.add(athlete)
            session.commit()
            session.refresh(athlete)
            
            return athlete.athlete_id
    
    # ========================================================================
    # MATCH RECORDING
    # ========================================================================
    
    def record_match(
        self,
        athlete_id: uuid.UUID,
        event_id: Optional[uuid.UUID],
        match_type: str,
        confidence: float,
        explanation: str,
        match_attributes: Optional[Dict] = None
    ):
        """
        Record entity match in database
        
        Args:
            athlete_id: Resolved athlete ID
            event_id: Optional event ID
            match_type: 'deterministic', 'probabilistic', or 'manual'
            confidence: Match confidence (0-1)
            explanation: Human-readable explanation
            match_attributes: Attributes used for matching
        """
        needs_review = confidence < self.REVIEW_THRESHOLD
        
        with self.storage.get_session() as session:
            match = EntityMatch(
                athlete_id=athlete_id,
                event_id=event_id,
                match_type=match_type,
                match_confidence=confidence,
                match_explanation=explanation,
                match_attributes=match_attributes,
                needs_review=needs_review
            )
            
            session.add(match)
            session.commit()
