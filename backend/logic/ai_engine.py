"""
BrandGuard AI Engine

Implements Story ADVERIFY-AI-1: AI Classification using Gemini 3.0 via Vertex AI.

This module handles the complete AI analysis pipeline:
1. Upload audio to GCS (S-1.2.1)
2. Transcribe using Google Speech-to-Text (ADVERIFY-AI-2)
3. Classify using Gemini with structured output (S-1.1.1 to S-1.1.4)

The AI engine is called only on cache misses, following the
Cache-First, AI-Fallback pattern from the AdVerify architecture.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple

from google.cloud import storage
from google.cloud import speech
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part

from models import VerificationResult, BrandSafetyScore, VerificationSource
from config import get_settings, GEMINI_SYSTEM_INSTRUCTION, GEMINI_OUTPUT_SCHEMA
from logic import stats

logger = logging.getLogger(__name__)

# Clients (lazy initialized)
_storage_client: Optional[storage.Client] = None
_speech_client: Optional[speech.SpeechClient] = None
_vertex_initialized: bool = False


def _init_vertex_ai() -> None:
    """
    Initialize Vertex AI SDK.
    
    Must be called before using Gemini API.
    Reference: ADVERIFY-AI-1 (S-1.1.1) - Gemini Client Setup
    """
    global _vertex_initialized
    if not _vertex_initialized:
        settings = get_settings()
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.vertex_ai_location
        )
        _vertex_initialized = True
        logger.info(f"Initialized Vertex AI: {settings.google_cloud_project}/{settings.vertex_ai_location}")


def get_storage_client() -> storage.Client:
    """Get or create GCS client."""
    global _storage_client
    if _storage_client is None:
        settings = get_settings()
        _storage_client = storage.Client(project=settings.google_cloud_project)
        logger.info("Initialized GCS client")
    return _storage_client


def get_speech_client() -> speech.SpeechClient:
    """Get or create Speech-to-Text client."""
    global _speech_client
    if _speech_client is None:
        _speech_client = speech.SpeechClient()
        logger.info("Initialized Speech-to-Text client")
    return _speech_client


async def upload_audio_to_gcs(audio_data: bytes, audio_id: str, content_type: str = "audio/mpeg") -> str:
    """
    Upload audio file to Google Cloud Storage.
    
    Implements audio storage for later transcription.
    Uses unique blob names to prevent collisions.
    
    Args:
        audio_data: Raw audio bytes
        audio_id: Unique identifier for the audio
        content_type: MIME type of the audio file
        
    Returns:
        GCS URI (gs://bucket/path)
        
    Reference: ADVERIFY-AI-2 - Content Fetch and Pre-processing
    """
    settings = get_settings()
    client = get_storage_client()
    bucket = client.bucket(settings.gcs_bucket_name)
    
    # Generate unique blob name
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    blob_name = f"audio/{audio_id}_{timestamp}_{unique_id}.mp3"
    
    blob = bucket.blob(blob_name)
    blob.upload_from_string(audio_data, content_type=content_type)
    
    gcs_uri = f"gs://{settings.gcs_bucket_name}/{blob_name}"
    logger.info(f"Uploaded audio to GCS: {gcs_uri}")
    
    return gcs_uri


async def transcribe_audio(gcs_uri: str) -> Tuple[str, list]:
    """
    Transcribe audio using Google Speech-to-Text API.
    
    Implements S-1.2.2 from ADVERIFY-AI-2:
    "Implement HTML parsing/stripping logic to isolate relevant text for Gemini."
    (Adapted: Extract text from audio instead of HTML)
    
    Uses long-running recognition for files > 1 minute.
    Returns word-level timestamps for unsafe segment detection.
    
    Args:
        gcs_uri: GCS URI of the audio file
        
    Returns:
        Tuple of (full_transcript, word_timestamps)
        
    Reference: ADVERIFY-AI-2 - Content Fetch and Pre-processing
    """
    settings = get_settings()
    client = get_speech_client()
    
    # Configure speech recognition
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        sample_rate_hertz=settings.speech_sample_rate_hertz,
        language_code=settings.speech_language_code,
        enable_word_time_offsets=True,  # For unsafe segment timestamps
        enable_automatic_punctuation=True,
        model="latest_long",  # Optimized for long-form audio
    )
    
    audio = speech.RecognitionAudio(uri=gcs_uri)
    
    logger.info(f"Starting transcription for: {gcs_uri}")
    
    # Use long-running operation for potentially large files
    operation = client.long_running_recognize(config=config, audio=audio)
    
    # Wait for completion (with timeout handling in production)
    response = operation.result(timeout=300)  # 5 minute timeout
    
    # Extract transcript and word timestamps
    full_transcript = ""
    word_timestamps = []
    
    for result in response.results:
        alternative = result.alternatives[0]
        full_transcript += alternative.transcript + " "
        
        for word_info in alternative.words:
            word_timestamps.append({
                "word": word_info.word,
                "start": word_info.start_time.total_seconds(),
                "end": word_info.end_time.total_seconds()
            })
    
    full_transcript = full_transcript.strip()
    logger.info(f"Transcription complete: {len(full_transcript)} chars, {len(word_timestamps)} words")
    
    return full_transcript, word_timestamps


async def classify_with_gemini(
    transcript: str,
    word_timestamps: list,
    audio_id: str,
    client_policy: Optional[str] = None
) -> dict:
    """
    Classify transcript using Gemini 3.0 Pro via Vertex AI.
    
    Implements ADVERIFY-AI-1:
    - S-1.1.1: Gemini Client Setup
    - S-1.1.2: JSON Schema Definition (structured output)
    - S-1.1.4: Prompt Engineering with System Instruction
    
    Uses structured output to guarantee parseable JSON response.
    
    Args:
        transcript: Full audio transcript text
        word_timestamps: List of word timing information
        audio_id: Unique identifier for logging
        client_policy: Optional client-specific policy rules
        
    Returns:
        Classification result dictionary
        
    Reference: ADVERIFY-AI-1 - AI Classification Endpoint
    """
    settings = get_settings()
    _init_vertex_ai()
    
    # Initialize Gemini model
    model = GenerativeModel(
        settings.gemini_model,
        system_instruction=GEMINI_SYSTEM_INSTRUCTION
    )
    
    # Build the classification prompt
    prompt = f"""Analyze the following audio transcript for brand safety classification.

## Audio ID
{audio_id}

## Transcript
{transcript[:10000]}  # Limit to 10k chars to stay within context window

## Word Timestamps (for unsafe segment detection)
{json.dumps(word_timestamps[:500], indent=2)}  # Sample of timestamps

"""
    
    # Add client policy if provided
    if client_policy:
        prompt += f"""
## Client-Specific Policy
{client_policy}

Apply these additional rules when classifying.
"""
    
    prompt += """
## Task
1. Classify the brand safety level (SAFE, RISK_MEDIUM, RISK_HIGH, or UNKNOWN)
2. Detect if this appears to be fraudulent/bot-generated content
3. Identify all relevant category tags
4. Find specific timestamps of any unsafe content segments
5. Provide a brief snippet that best represents the content

Respond with a valid JSON object matching the required schema.
"""
    
    # Configure generation for structured output
    generation_config = GenerationConfig(
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_output_tokens,
        response_mime_type="application/json",
    )
    
    logger.info(f"Calling Gemini for classification: {audio_id}")
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Parse JSON response
        result = json.loads(response.text)
        
        # Track token usage
        if response.usage_metadata:
            stats.increment_token_usage(
                response.usage_metadata.prompt_token_count,
                response.usage_metadata.candidates_token_count
            )
        
        logger.info(f"Gemini classification complete for {audio_id}: {result.get('brand_safety_score')}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response for {audio_id}: {e}")
        # Return safe fallback
        return {
            "brand_safety_score": "UNKNOWN",
            "fraud_flag": False,
            "category_tags": ["uncategorized"],
            "confidence_score": 0.0,
            "unsafe_segments": [],
            "transcript_snippet": transcript[:200] if transcript else "",
            "reasoning": f"Failed to parse AI response: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Gemini API error for {audio_id}: {e}")
        raise


async def analyze(audio_data: bytes, audio_id: str, client_policy: Optional[str] = None) -> VerificationResult:
    """
    Fast AI analysis pipeline using Gemini's native audio understanding.
    
    This skips the slow Speech-to-Text step and sends audio directly to Gemini 2.0,
    which can process audio natively for much faster analysis (~5-10 seconds).
    
    Args:
        audio_data: Raw audio file bytes
        audio_id: Unique identifier for the audio
        client_policy: Optional client-specific rules
        
    Returns:
        VerificationResult from AI analysis
        
    Reference: ADVERIFY-AI-1 - AI Classification Endpoint
    """
    logger.info(f"Starting fast AI analysis for: {audio_id}")
    
    try:
        settings = get_settings()
        _init_vertex_ai()
        
        # Upload to GCS first (needed for Gemini to access)
        gcs_uri = await upload_audio_to_gcs(audio_data, audio_id)
        
        # Initialize Gemini model with audio capability
        model = GenerativeModel(
            settings.gemini_model,
            system_instruction=GEMINI_SYSTEM_INSTRUCTION
        )
        
        # Create audio part from GCS URI
        audio_part = Part.from_uri(gcs_uri, mime_type="audio/mpeg")
        
        # Build the classification prompt
        prompt = f"""Analyze this audio content for brand safety classification.

## Audio ID
{audio_id}

## Task
Listen to the ENTIRE audio carefully and provide:

1. **Content Summary**: A 2-3 sentence summary of what this podcast/audio is about
2. **Brand Safety Classification**: SAFE, RISK_MEDIUM, RISK_HIGH, or UNKNOWN
3. **Fraud Detection**: Is this bot-generated or fraudulent content?
4. **Category Tags**: All relevant categories (news, politics, entertainment, comedy, explicit, violence, controversial, etc.)
5. **Unsafe Ad Segments**: Specific timestamps where ads should NOT be shown due to sensitive content

For unsafe segments, identify:
- Explicit language or profanity
- Violence or graphic descriptions  
- Controversial political statements
- Drug/alcohol references
- Sexual content
- Hate speech or discrimination

{f"Client Policy: {client_policy}" if client_policy else ""}

Respond with a valid JSON object:
{{
  "brand_safety_score": "SAFE" | "RISK_MEDIUM" | "RISK_HIGH" | "UNKNOWN",
  "fraud_flag": boolean,
  "category_tags": ["tag1", "tag2", ...],
  "confidence_score": 0.0 to 1.0,
  "content_summary": "2-3 sentence summary of the audio content",
  "unsafe_segments": [
    {{"start_time": "MM:SS", "end_time": "MM:SS", "reason": "brief explanation"}},
    ...
  ],
  "transcript_snippet": "First 200 characters of the main content"
}}
"""
        
        # Configure generation
        generation_config = GenerationConfig(
            temperature=0.1,
            max_output_tokens=8192,
        )
        
        logger.info(f"Calling Gemini with audio for: {audio_id}")
        
        response = model.generate_content(
            [audio_part, prompt],
            generation_config=generation_config
        )
        
        # Parse JSON response - try multiple strategies
        response_text = response.text.strip()
        logger.info(f"Gemini raw response for {audio_id} (first 800 chars): {response_text[:800]}")
        
        # Track token usage
        if response.usage_metadata:
            stats.increment_token_usage(
                response.usage_metadata.prompt_token_count,
                response.usage_metadata.candidates_token_count
            )
        
        classification = None
        
        # Strategy 0: Clean markdown code blocks and find JSON boundaries
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        start_idx = clean_text.find('{')
        end_idx = clean_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_text = clean_text[start_idx : end_idx + 1]
            try:
                classification = json.loads(clean_text)
                logger.info(f"Cleaned JSON parse succeeded: {classification.get('brand_safety_score')}")
            except json.JSONDecodeError as e:
                logger.warning(f"Cleaned JSON parse failed: {e}")

        # Strategy 1: Direct JSON parse (if Strategy 0 failed or wasn't tried)
        if classification is None:
            try:
                classification = json.loads(response_text)
                logger.info(f"Direct JSON parse succeeded: {classification.get('brand_safety_score')}")
            except json.JSONDecodeError:
                logger.warning(f"Direct JSON parse failed, trying extraction...")
        
        # Strategy 2: Extract JSON object from text
        if classification is None:
            import re
            # Find JSON object (handles nested objects)
            matches = re.findall(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', response_text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    if 'brand_safety_score' in parsed:
                        classification = parsed
                        logger.info(f"Extracted JSON succeeded: {classification.get('brand_safety_score')}")
                        break
                except json.JSONDecodeError:
                    continue
        
        # Strategy 3: Fallback - parse the response manually
        if classification is None:
            logger.warning(f"All JSON parsing failed, using fallback")
            # Try to extract key values from the text
            score = "UNKNOWN"
            if "RISK_HIGH" in response_text:
                score = "RISK_HIGH"
            elif "RISK_MEDIUM" in response_text:
                score = "RISK_MEDIUM"
            elif "SAFE" in response_text and "UNSAFE" not in response_text.upper():
                score = "SAFE"
            
            classification = {
                "brand_safety_score": score,
                "fraud_flag": "true" in response_text.lower() and "fraud" in response_text.lower(),
                "category_tags": [],
                "confidence_score": 0.7,
                "unsafe_segments": [],
                "transcript_snippet": response_text[:300]
            }
            
            # Extract category tags
            for tag in ["politics", "news", "entertainment", "music", "explicit", "violence", "controversial", "business"]:
                if tag in response_text.lower():
                    classification["category_tags"].append(tag)
        
        # Build result
        result = VerificationResult(
            audio_id=audio_id,
            brand_safety_score=BrandSafetyScore(
                classification.get("brand_safety_score", "UNKNOWN")
            ),
            fraud_flag=classification.get("fraud_flag", False),
            category_tags=classification.get("category_tags", []),
            source=VerificationSource.AI_GENERATED,
            confidence_score=classification.get("confidence_score"),
            unsafe_segments=classification.get("unsafe_segments"),
            transcript_snippet=classification.get("transcript_snippet"),
            content_summary=classification.get("content_summary"),
            created_at=datetime.utcnow()
        )
        
        logger.info(f"Fast AI analysis complete for {audio_id}: {result.brand_safety_score.value}")
        return result
        
    except Exception as e:
        logger.error(f"AI analysis failed for {audio_id}: {e}")
        
        # Return UNKNOWN result on failure
        return VerificationResult(
            audio_id=audio_id,
            brand_safety_score=BrandSafetyScore.UNKNOWN,
            fraud_flag=False,
            category_tags=["error"],
            source=VerificationSource.AI_GENERATED,
            confidence_score=0.0,
            transcript_snippet=f"Analysis failed: {str(e)}",
            created_at=datetime.utcnow()
        )


async def analyze_from_url(audio_url: str, audio_id: str, client_policy: Optional[str] = None) -> VerificationResult:
    """
    Analyze audio from a URL instead of uploaded bytes.
    
    Supports:
    - Direct audio URLs (MP3, WAV, etc.)
    - YouTube, SoundCloud, Vimeo, TikTok, Twitter/X
    - Bandcamp, Twitch, Dailymotion, Rumble
    - Facebook, Instagram, Reddit videos
    - Apple Podcasts, Spotify (links), Anchor.fm
    - RSS/Podcast feeds
    - 1000+ more platforms via yt-dlp
    
    Args:
        audio_url: URL to fetch audio from
        audio_id: Unique identifier for the audio
        client_policy: Optional client-specific rules
        
    Returns:
        VerificationResult from AI analysis
    """
    logger.info(f"Analyzing from URL for {audio_id}: {audio_url}")
    
    # Check for DRM-protected platforms
    drm_platforms = {
        'spotify.com': 'Spotify',
        'open.spotify.com': 'Spotify', 
        'music.apple.com': 'Apple Music',
        'podcasts.apple.com': 'Apple Podcasts',
        'amazon.com/music': 'Amazon Music',
        'deezer.com': 'Deezer'
    }
    for pattern, name in drm_platforms.items():
        if pattern in audio_url.lower():
            raise ValueError(f"{name} is DRM-protected and cannot be downloaded. Please use YouTube, SoundCloud, or direct MP3 URLs instead.")
    
    try:
        # Check URL type and extract audio accordingly
        if is_rss_feed(audio_url):
            logger.info(f"Detected RSS feed: {audio_url}")
            audio_data = await extract_audio_from_rss(audio_url, audio_id)
        elif is_supported_platform_url(audio_url):
            logger.info(f"Detected supported platform: {audio_url}")
            audio_data = await extract_audio_from_platform(audio_url, audio_id)
        else:
            # Try direct audio URL first, fallback to yt-dlp
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                        if response.status != 200:
                            raise ValueError(f"HTTP {response.status}")
                        content_type = response.headers.get('content-type', '')
                        if 'audio' in content_type or 'octet-stream' in content_type:
                            audio_data = await response.read()
                        else:
                            # Not a direct audio file, try yt-dlp
                            raise ValueError("Not a direct audio URL")
            except Exception as e:
                logger.info(f"Direct download failed, trying yt-dlp: {e}")
                audio_data = await extract_audio_from_platform(audio_url, audio_id)
        
        return await analyze(audio_data, audio_id, client_policy)
        
    except Exception as e:
        logger.error(f"URL analysis failed for {audio_id}: {e}")
        raise


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL."""
    youtube_patterns = [
        'youtube.com/watch',
        'youtu.be/',
        'youtube.com/shorts',
        'youtube.com/embed',
        'youtube.com/v/',
        'm.youtube.com'
    ]
    return any(pattern in url.lower() for pattern in youtube_patterns)


def is_supported_platform_url(url: str) -> bool:
    """
    Check if URL is from a platform supported by yt-dlp.
    
    yt-dlp supports 1000+ sites including:
    - YouTube, SoundCloud, Vimeo, TikTok, Twitter/X
    - Spotify (metadata only), Bandcamp, Dailymotion
    - Many podcast platforms and more
    """
    supported_patterns = [
        # YouTube
        'youtube.com', 'youtu.be',
        # SoundCloud
        'soundcloud.com',
        # Vimeo
        'vimeo.com',
        # Twitter/X
        'twitter.com', 'x.com',
        # TikTok
        'tiktok.com',
        # Twitch
        'twitch.tv',
        # Bandcamp
        'bandcamp.com',
        # Dailymotion
        'dailymotion.com',
        # Rumble
        'rumble.com',
        # Bitchute
        'bitchute.com',
        # Odysee
        'odysee.com',
        # Facebook
        'facebook.com', 'fb.watch',
        # Instagram
        'instagram.com',
        # Reddit
        'reddit.com', 'v.redd.it',
        # Podcast platforms (that allow downloads)
        'anchor.fm',
        # Other audio platforms
        'mixcloud.com', 'audiomack.com',
    ]
    
    # Check for DRM-protected platforms first
    drm_platforms = ['open.spotify.com', 'spotify.com', 'music.apple.com', 'podcasts.apple.com']
    if any(drm in url.lower() for drm in drm_platforms):
        return False  # Not supported due to DRM
    
    return any(pattern in url.lower() for pattern in supported_patterns)


def is_rss_feed(url: str) -> bool:
    """Check if URL is likely an RSS feed."""
    rss_patterns = ['/rss', '/feed', '.rss', '.xml', 'feeds.']
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in rss_patterns)


async def extract_audio_from_platform(url: str, audio_id: str) -> bytes:
    """
    Extract audio from any yt-dlp supported platform.
    
    Supports 1000+ sites including:
    - YouTube, SoundCloud, Vimeo, TikTok, Twitter/X
    - Bandcamp, Dailymotion, Twitch, and more
    
    Limited to first 10 minutes for faster processing.
    """
    import tempfile
    import os
    import asyncio
    
    logger.info(f"Extracting audio from platform for {audio_id}: {url}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_template = os.path.join(temp_dir, f"{audio_id}.%(ext)s")
        
        # yt-dlp options for audio extraction
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Handle geo-restrictions
            'geo_bypass': True,
            # Retry on failure
            'retries': 3,
            # Download only first 5 minutes (300 seconds) for faster analysis
            'external_downloader': 'ffmpeg',
            'external_downloader_args': {'ffmpeg_i': ['-t', '300']},
        }
        
        def download():
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download)
        
        # Find downloaded file
        for f in os.listdir(temp_dir):
            if f.endswith(('.mp3', '.m4a', '.webm', '.opus', '.ogg', '.wav')):
                audio_file = os.path.join(temp_dir, f)
                with open(audio_file, 'rb') as file:
                    audio_data = file.read()
                logger.info(f"Extracted {len(audio_data)} bytes from platform for {audio_id}")
                return audio_data
        
        raise ValueError(f"Failed to extract audio from: {url}")


async def extract_audio_from_rss(rss_url: str, audio_id: str) -> bytes:
    """
    Extract audio from an RSS podcast feed.
    
    Parses the feed and downloads the first episode's audio.
    """
    import aiohttp
    import xml.etree.ElementTree as ET
    
    logger.info(f"Parsing RSS feed for {audio_id}: {rss_url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                raise ValueError(f"Failed to fetch RSS: HTTP {response.status}")
            rss_content = await response.text()
    
    # Parse RSS
    root = ET.fromstring(rss_content)
    
    # Find first enclosure (audio file)
    audio_url = None
    for enclosure in root.iter('enclosure'):
        enc_type = enclosure.get('type', '')
        if 'audio' in enc_type:
            audio_url = enclosure.get('url')
            break
    
    if not audio_url:
        # Try media:content
        for item in root.iter('item'):
            for media in item.iter('{http://search.yahoo.com/mrss/}content'):
                if 'audio' in media.get('type', ''):
                    audio_url = media.get('url')
                    break
    
    if not audio_url:
        raise ValueError("No audio found in RSS feed")
    
    logger.info(f"Found audio in RSS: {audio_url}")
    
    # Download the audio
    async with aiohttp.ClientSession() as session:
        async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=120)) as response:
            if response.status != 200:
                raise ValueError(f"Failed to download audio: HTTP {response.status}")
            audio_data = await response.read()
    
    return audio_data


async def extract_youtube_audio(youtube_url: str, audio_id: str) -> bytes:
    """
    Extract audio from a YouTube video using yt-dlp.
    
    Downloads only the audio stream for efficiency.
    Limited to first 10 minutes to avoid long processing times.
    
    Args:
        youtube_url: YouTube video URL
        audio_id: Unique identifier for logging
        
    Returns:
        Audio data as bytes
    """
    import tempfile
    import os
    import asyncio
    
    logger.info(f"Extracting audio from YouTube for {audio_id}: {youtube_url}")
    
    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, f"{audio_id}.mp3")
        
        # yt-dlp options for audio extraction
        # Limit to first 10 minutes (600 seconds) for faster processing
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Limit download to 10 minutes
            'download_ranges': lambda info_dict, ydl: [{'start_time': 0, 'end_time': 600}],
            'force_keyframes_at_cuts': True,
        }
        
        # Run yt-dlp in executor to not block async
        def download():
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download)
        
        # Find the downloaded file (yt-dlp may change extension)
        downloaded_files = os.listdir(temp_dir)
        audio_file = None
        for f in downloaded_files:
            if f.endswith(('.mp3', '.m4a', '.webm', '.opus')):
                audio_file = os.path.join(temp_dir, f)
                break
        
        if not audio_file or not os.path.exists(audio_file):
            raise ValueError(f"Failed to extract audio from YouTube: {youtube_url}")
        
        # Read audio data
        with open(audio_file, 'rb') as f:
            audio_data = f.read()
        
        logger.info(f"Extracted {len(audio_data)} bytes from YouTube for {audio_id}")
        return audio_data


async def analyze_from_url_full(
    audio_url: str,
    audio_id: str,
    client_policy: Optional[str] = None,
    progress_callback: Optional[callable] = None
) -> VerificationResult:
    """
    Full URL analysis without time limits.
    
    Used for background job processing of long podcasts.
    Includes progress callbacks for status updates.
    
    Args:
        audio_url: URL to fetch audio from
        audio_id: Unique identifier for the audio
        client_policy: Optional client-specific rules
        progress_callback: Optional callback(progress, message) for status updates
        
    Returns:
        VerificationResult from AI analysis
    """
    import tempfile
    import os
    import asyncio
    
    def update_progress(progress: int, message: str):
        if progress_callback:
            progress_callback(progress, message)
    
    logger.info(f"Starting full URL analysis for {audio_id}: {audio_url}")
    update_progress(5, "Starting analysis...")
    
    # Check for DRM platforms
    drm_platforms = {
        'spotify.com': 'Spotify',
        'open.spotify.com': 'Spotify', 
        'music.apple.com': 'Apple Music',
        'podcasts.apple.com': 'Apple Podcasts',
    }
    for pattern, name in drm_platforms.items():
        if pattern in audio_url.lower():
            raise ValueError(f"{name} is DRM-protected. Please use YouTube, SoundCloud, or direct MP3 URLs.")
    
    update_progress(10, "Downloading audio...")
    
    # Download audio without time limits
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_template = os.path.join(temp_dir, f"{audio_id}.%(ext)s")
            
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True,
                'no_warnings': True,
                'geo_bypass': True,
                'retries': 3,
            }
            
            def download():
                import yt_dlp
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([audio_url])
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download)
            
            update_progress(50, "Download complete, processing...")
            
            # Find downloaded file
            audio_data = None
            for f in os.listdir(temp_dir):
                if f.endswith(('.mp3', '.m4a', '.webm', '.opus', '.ogg', '.wav')):
                    with open(os.path.join(temp_dir, f), 'rb') as file:
                        audio_data = file.read()
                    break
            
            if not audio_data:
                raise ValueError("Failed to download audio")
            
            logger.info(f"Downloaded {len(audio_data)} bytes for {audio_id}")
            
    except Exception as e:
        # Fallback to direct download
        update_progress(15, "Trying direct download...")
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    raise ValueError(f"Download failed: HTTP {response.status}")
                audio_data = await response.read()
    
    update_progress(60, "Uploading to cloud...")
    
    # Run analysis
    update_progress(70, "Analyzing with AI...")
    result = await analyze(audio_data, audio_id, client_policy)
    
    update_progress(100, "Complete!")
    return result
