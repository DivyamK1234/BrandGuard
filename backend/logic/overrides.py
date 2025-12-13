"""
BrandGuard Overrides Logic

Implements Story ADVERIFY-UI-1 (S-2.1.4): Backend Integration for Override Lookup.

Manual overrides take the highest priority in the lookup chain:
Override > Cache > AI Generated

The overrides are stored in Google Firestore for:
- Real-time sync across service instances
- Audit trail and persistence
- Quick lookup by audio_id
"""

import logging
from typing import Optional, List
from datetime import datetime

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from models import VerificationResult, BrandSafetyScore, VerificationSource, OverrideRecord
from config import get_settings

logger = logging.getLogger(__name__)

# Firestore client (lazy initialized)
_firestore_client: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
    """
    Get or create Firestore client.
    
    Uses lazy initialization to avoid connection issues during import.
    Reference: GCP Best Practices - Client lifecycle management
    """
    global _firestore_client
    if _firestore_client is None:
        settings = get_settings()
        _firestore_client = firestore.Client(project=settings.google_cloud_project)
        logger.info(f"Initialized Firestore client for project: {settings.google_cloud_project}")
    return _firestore_client


def check_override(audio_id: str) -> Optional[VerificationResult]:
    """
    Check if a manual override exists for the given audio_id.
    
    Implements Logic S-2.1.4 from AdVerify Docs:
    "Update the Core Lookup Logic (BE-1) to check the high-priority
    Override Database before checking the main In-Memory Cache."
    
    Args:
        audio_id: Unique identifier for the audio file
        
    Returns:
        VerificationResult if override exists, None otherwise
        
    Reference: ADVERIFY-UI-1 - Override takes effect within 60 seconds
    """
    settings = get_settings()
    
    try:
        db = get_firestore_client()
        doc_ref = db.collection(settings.firestore_collection_overrides).document(audio_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            logger.info(f"Override found for audio_id: {audio_id}")
            
            # Convert Firestore data to VerificationResult
            return VerificationResult(
                audio_id=audio_id,
                brand_safety_score=BrandSafetyScore(data.get("brand_safety_score", "UNKNOWN")),
                fraud_flag=data.get("fraud_flag", False),
                category_tags=data.get("category_tags", []),
                source=VerificationSource.MANUAL_OVERRIDE,
                confidence_score=1.0,  # Manual overrides have 100% confidence
                unsafe_segments=data.get("unsafe_segments"),
                transcript_snippet=data.get("transcript_snippet"),
                created_at=data.get("created_at", datetime.utcnow())
            )
        
        logger.debug(f"No override found for audio_id: {audio_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error checking override for {audio_id}: {e}")
        # On error, return None to fall through to cache/AI
        # This prevents overrides DB issues from blocking requests
        return None


def create_override(override: OverrideRecord) -> OverrideRecord:
    """
    Create a new manual override in Firestore.
    
    Implements S-2.1.3: Management API - Create operation
    
    Args:
        override: Override record to create
        
    Returns:
        Created override record with timestamps
    """
    settings = get_settings()
    db = get_firestore_client()
    
    override.created_at = datetime.utcnow()
    override.updated_at = datetime.utcnow()
    
    doc_ref = db.collection(settings.firestore_collection_overrides).document(override.audio_id)
    doc_ref.set(override.model_dump())
    
    logger.info(f"Created override for audio_id: {override.audio_id} by {override.created_by}")
    return override


def update_override(audio_id: str, override: OverrideRecord) -> Optional[OverrideRecord]:
    """
    Update an existing manual override in Firestore.
    
    Implements S-2.1.3: Management API - Update operation
    
    Args:
        audio_id: Audio file ID to update
        override: Updated override data
        
    Returns:
        Updated override record, or None if not found
    """
    settings = get_settings()
    db = get_firestore_client()
    
    doc_ref = db.collection(settings.firestore_collection_overrides).document(audio_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        logger.warning(f"Override not found for update: {audio_id}")
        return None
    
    override.updated_at = datetime.utcnow()
    # Preserve original creation time
    original_data = doc.to_dict()
    override.created_at = original_data.get("created_at", datetime.utcnow())
    
    doc_ref.update(override.model_dump())
    
    logger.info(f"Updated override for audio_id: {audio_id}")
    return override


def delete_override(audio_id: str) -> bool:
    """
    Delete a manual override from Firestore.
    
    Implements S-2.1.3: Management API - Delete operation
    
    Args:
        audio_id: Audio file ID to delete override for
        
    Returns:
        True if deleted, False if not found
    """
    settings = get_settings()
    db = get_firestore_client()
    
    doc_ref = db.collection(settings.firestore_collection_overrides).document(audio_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        logger.warning(f"Override not found for deletion: {audio_id}")
        return False
    
    doc_ref.delete()
    logger.info(f"Deleted override for audio_id: {audio_id}")
    return True


def list_overrides(limit: int = 100, offset: int = 0) -> List[OverrideRecord]:
    """
    List all manual overrides with pagination.
    
    Implements S-2.1.1: UI Table & Search support
    
    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip
        
    Returns:
        List of override records
    """
    settings = get_settings()
    db = get_firestore_client()
    
    query = (
        db.collection(settings.firestore_collection_overrides)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .offset(offset)
    )
    
    docs = query.stream()
    overrides = []
    
    for doc in docs:
        data = doc.to_dict()
        overrides.append(OverrideRecord(
            audio_id=data.get("audio_id", doc.id),
            brand_safety_score=BrandSafetyScore(data.get("brand_safety_score", "UNKNOWN")),
            fraud_flag=data.get("fraud_flag", False),
            category_tags=data.get("category_tags", []),
            reason=data.get("reason"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow())
        ))
    
    logger.debug(f"Listed {len(overrides)} overrides (limit={limit}, offset={offset})")
    return overrides


def search_overrides(query: str, limit: int = 50) -> List[OverrideRecord]:
    """
    Search overrides by audio_id prefix.
    
    Implements S-2.1.1: UI Table & Search - Search/filtering
    
    Note: Firestore has limited text search. For production, consider
    using Algolia or Elasticsearch for full-text search.
    
    Args:
        query: Search query (audio_id prefix)
        limit: Maximum results
        
    Returns:
        Matching override records
    """
    settings = get_settings()
    db = get_firestore_client()
    
    # Firestore prefix search using range query
    end_query = query + '\uf8ff'  # Unicode high character for prefix matching
    
    docs = (
        db.collection(settings.firestore_collection_overrides)
        .where(filter=FieldFilter("audio_id", ">=", query))
        .where(filter=FieldFilter("audio_id", "<=", end_query))
        .limit(limit)
        .stream()
    )
    
    overrides = []
    for doc in docs:
        data = doc.to_dict()
        overrides.append(OverrideRecord(
            audio_id=data.get("audio_id", doc.id),
            brand_safety_score=BrandSafetyScore(data.get("brand_safety_score", "UNKNOWN")),
            fraud_flag=data.get("fraud_flag", False),
            category_tags=data.get("category_tags", []),
            reason=data.get("reason"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow())
        ))
    
    logger.debug(f"Search for '{query}' returned {len(overrides)} results")
    return overrides
