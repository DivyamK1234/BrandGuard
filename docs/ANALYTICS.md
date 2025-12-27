# Analytics Dashboard

## Overview

The **Analytics Dashboard** is a real-time monitoring system that tracks and visualizes BrandGuard verification metrics. It provides comprehensive insights into:

- **Total verifications** and daily activity
- **Success rates** (Safe vs. Unsafe classifications)
- **Processing performance** (average response times)
- **Classification breakdown** (Safe, Risk Medium, Risk High, Unknown)
- **7-day trend analysis**
- **Recent verification history**

## Architecture

### Frontend-Backend Communication (Proxy Pattern)
To ensure secure and reliable communication between the Frontend and Backend (especially in containerized environments like Docker and Cloud Run), we use a **Next.js API Proxy**:

1. **Frontend Component** (e.g., `AnalyticsDashboard.tsx`) makes a relative call: `GET /api/v1/analytics`
2. **Next.js Server** receives the request and proxies it to the backend Service using `BACKEND_URL`:
   - **Local:** `http://backend:8000/api/v1/analytics`
   - **Cloud Run:** `https://your-backend-url/api/v1/analytics`
3. **Backend API** (FastAPI) processes the request and returns data.

**Benefits:**
- **Security:** Hides the internal backend URL from the public browser.
- **CORS:** Eliminates Cross-Origin Resource Sharing (CORS) issues completely.
- **Networking:** Handles Docker's internal DNS resolution server-side.

### Backend Components

#### 1. Analytics Engine (`backend/logic/analytics.py`)

The analytics engine uses **Redis** to store and aggregate metrics:

```python
from logic.analytics import get_analytics_engine

engine = get_analytics_engine()
engine.track_verification(
    audio_id="audio_123",
    brand_safety_score=BrandSafetyScore.SAFE,
    source=VerificationSource.AI_GENERATED,
    processing_time_ms=234.5,
    fraud_flag=False,
    category_tags=["NEWS", "POLITICS"]
)
```

**Redis Data Structure:**
- `analytics:stats` - Global statistics (total count, averages, breakdowns)
- `analytics:recent` - FIFO list of last 50 verifications
- `analytics:daily:YYYY-MM-DD` - Daily aggregated stats for trend analysis

**TTLs:**
- Global stats: 30 days
- Recent verifications: 7 days
- Daily stats: 30 days

#### 2. API Endpoint (`/api/v1/analytics`)

Returns comprehensive analytics summary:

```json
{
  "total_verifications": 1234,
  "today_count": 124,
  "success_rate": 89.5,
  "avg_processing_time_ms": 234.2,
  "fraud_detections": 12,
  "classification_breakdown": {
    "SAFE": 1100,
    "RISK_HIGH": 50,
    "RISK_MEDIUM": 70,
    "UNKNOWN": 14
  },
  "classification_percentages": {
    "safe": 89.1,
    "risk_high": 4.1,
    "risk_medium": 5.7,
    "unknown": 1.1
  },
  "source_breakdown": {
    "AI_GENERATED": 800,
    "CACHE": 400,
    "MANUAL_OVERRIDE": 34
  },
  "recent_verifications": [...],
  "trend_data": [...],
  "last_updated": "2024-12-27T18:30:00Z"
}
```

### Frontend Components

#### 1. Analytics Dashboard (`frontend/components/AnalyticsDashboard.tsx`)

React component with real-time updates:

**Features:**
- ✅ Auto-refresh every 5 seconds
- ✅ 4 key metric cards
- ✅ Classification breakdown with progress bars
- ✅ 7-day trend chart (bar chart)
- ✅ Recent verifications table
- ✅ Loading and error states

**Usage:**
```tsx
import AnalyticsDashboard from '@/components/AnalyticsDashboard'

function AnalyticsPage() {
  return <AnalyticsDashboard />
}
```

#### 2. Main Dashboard Integration (`frontend/app/page.tsx`)

Added as a third tab alongside "Demo Client" and "Admin Console":

```tsx
type TabType = 'demo' | 'admin' | 'analytics'
```

## Metrics Tracked

### 1. **Total Verifications**
- Lifetime count of all audio verifications
- Today's count for daily activity monitoring

### 2. **Success Rate**
- Percentage of verifications classified as `SAFE`
- Formula: `(SAFE count / total) * 100`

### 3. **Average Processing Time**
- Mean latency across all verifications
- Tracks last 1000 processing times for accuracy
- Measured in milliseconds

### 4. **Unsafe Detections**
- Count of `RISK_HIGH` classifications
- Fraud flag count

### 5. **Classification Breakdown**
- **SAFE**: Brand-safe content
- **RISK_MEDIUM**: Potentially sensitive content
- **RISK_HIGH**: Unsafe content (explicit, harmful)
- **UNKNOWN**: Unable to classify

### 6. **Source Breakdown**
- **AI_GENERATED**: Fresh AI analysis
- **CACHE**: Retrieved from Redis cache
- **MANUAL_OVERRIDE**: Admin-forced classification

### 7. **7-Day Trend**
- Daily verification counts for the last 7 days
- Breakdown by classification type per day

### 8. **Recent Verifications**
- Last 10 verifications with:
  - Audio ID
  - Classification result
  - Source (AI/Cache/Override)
  - Processing time
  - Timestamp

## Integration Points

### Automatic Tracking

Analytics tracking is automatically integrated into all verification flows:

#### 1. Override Hit
```python
# main.py line ~250
override_result = overrides.check_override(audio_id)
if override_result:
    analytics.get_analytics_engine().track_verification(...)
    return override_result
```

#### 2. Cache Hit
```python
# main.py line ~270
cached_result = cache.check_cache(audio_id)
if cached_result:
    analytics.get_analytics_engine().track_verification(...)
    return cached_result
```

#### 3. AI Analysis
```python
# main.py line ~300
result = await ai_engine.analyze(audio_data, audio_id, client_policy)
cache.set_cache(audio_id, result)
analytics.get_analytics_engine().track_verification(...)
return result
```

## API Reference

### GET `/api/v1/analytics`

**Description:** Retrieve complete analytics summary

**Response:** `200 OK`
```json
{
  "total_verifications": number,
  "today_count": number,
  "success_rate": number,
  "avg_processing_time_ms": number,
  "fraud_detections": number,
  "classification_breakdown": {...},
  "classification_percentages": {...},
  "source_breakdown": {...},
  "recent_verifications": [...],
  "trend_data": [...],
  "last_updated": string
}
```

**Error:** `500 Internal Server Error`
```json
{
  "detail": "Analytics error: <error message>"
}
```

## Usage Examples

### Viewing the Dashboard

1. **Start the application:**
   ```bash
   docker compose up -d
   ```

2. **Open the frontend:**
   ```
   http://localhost:3000
   ```

3. **Navigate to Analytics tab:**
   - Click the "Analytics" tab in the navigation bar
   - Dashboard will auto-load and refresh every 5 seconds

### Generating Test Data

To populate the dashboard with sample data:

```bash
# Upload several audio files via the Demo Client tab
# Or use the API directly:

curl -X POST http://localhost:8000/api/v1/verify_audio \
  -F "audio_file=@sample.mp3" \
  -F "audio_id=test_001"
```

### Resetting Analytics (Testing)

```python
from logic.analytics import get_analytics_engine

engine = get_analytics_engine()
engine.reset_stats()  # Clears all analytics data
```

## Performance Considerations

### Redis Memory Usage

- **Global stats**: ~1 KB
- **Recent verifications** (50 items): ~10 KB
- **Daily stats** (30 days): ~5 KB
- **Total**: ~16 KB per deployment

### API Latency

- **Target**: < 50ms
- **Actual**: ~10-20ms (Redis GET operations)
- **No impact** on verification flow (tracking is fire-and-forget)

### Frontend Refresh Rate

- **Default**: 5 seconds
- **Configurable** in `AnalyticsDashboard.tsx`:
  ```tsx
  const interval = setInterval(fetchAnalytics, 5000) // Change to 10000 for 10s
  ```

## Monitoring & Observability

### Prometheus Metrics

The analytics system integrates with existing Prometheus metrics:

```
# Verification counts by classification
brandguard_verifications_total{classification="SAFE"} 1100
brandguard_verifications_total{classification="RISK_HIGH"} 50

# Processing time histogram
brandguard_processing_time_ms_bucket{le="100"} 950
brandguard_processing_time_ms_bucket{le="500"} 1200
```

### Grafana Dashboard

Create a Grafana dashboard using the `/api/v1/analytics` endpoint:

1. Add a **JSON API** data source pointing to `http://backend:8000/api/v1/analytics`
2. Create panels for:
   - Total verifications (Stat panel)
   - Success rate (Gauge panel)
   - 7-day trend (Time series panel)
   - Classification breakdown (Pie chart)

### Jaeger Tracing

Analytics tracking operations are traced:

```
Span: analytics.track_verification
  - audio_id: audio_123
  - classification: SAFE
  - processing_time_ms: 234.5
  - duration: 2ms
```

## Troubleshooting

### Dashboard shows "No data available"

**Cause:** No verifications have been processed yet

**Solution:** Upload an audio file via the Demo Client tab

### Analytics endpoint returns 500 error

**Cause:** Redis connection failure

**Solution:**
1. Check Redis is running: `docker ps | grep redis`
2. Check Redis logs: `docker logs brandguard-redis-1`
3. Verify Redis connection in backend logs

### Metrics not updating

**Cause:** Analytics tracking not integrated

**Solution:** Ensure all verification endpoints call `track_verification()`

### Old data persists

**Cause:** Redis TTLs not expiring

**Solution:**
```bash
# Connect to Redis
docker exec -it brandguard-redis-1 redis-cli

# Check TTL
TTL analytics:stats

# Manually delete if needed
DEL analytics:stats
DEL analytics:recent
```

## Future Enhancements

### Planned Features

1. **Alerting**
   - Email/Slack notifications when unsafe rate exceeds threshold
   - Alert on processing time degradation

2. **Advanced Filtering**
   - Filter by date range
   - Filter by classification type
   - Search by audio ID

3. **Export Functionality**
   - CSV export of analytics data
   - PDF report generation

4. **Comparative Analysis**
   - Week-over-week comparison
   - Month-over-month trends

5. **Real-time WebSocket Updates**
   - Replace polling with WebSocket for instant updates
   - Live verification feed

## Contributing

To extend the analytics system:

1. **Add new metrics** in `analytics.py`:
   ```python
   def track_custom_metric(self, metric_name: str, value: float):
       self.client.hincrby("analytics:custom", metric_name, value)
   ```

2. **Update API response** in `main.py`:
   ```python
   @app.get("/api/v1/analytics")
   async def get_analytics():
       summary = engine.get_analytics_summary()
       summary["custom_metrics"] = engine.get_custom_metrics()
       return summary
   ```

3. **Add frontend visualization** in `AnalyticsDashboard.tsx`:
   ```tsx
   <MetricCard
       icon={<CustomIcon />}
       label="Custom Metric"
       value={data.custom_metrics.value}
   />
   ```

## License

This analytics feature is part of the BrandGuard project and follows the same license.

---

**Last Updated:** 2024-12-27  
**Version:** 1.0.0  
**Maintainer:** BrandGuard Team
