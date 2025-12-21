import json
import logging
from typing import Dict, Any, Optional

from confluent_kafka import Producer
from config import get_settings
import telemetry

logger = logging.getLogger(__name__)

class KafkaProducer:
    """
    Kafka Producer for BrandGuard.
    Handles sending job requests to Kafka for asynchronous processing.
    """
    
    def __init__(self):
        settings = get_settings()
        self.topic = settings.kafka_topic_jobs
        
        # Kafka configuration
        conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'client.id': 'brandguard-backend-producer',
            # Optimizing for reliability
            'acks': 'all',
            'retries': 5,
            'retry.backoff.ms': 500,
        }
        
        try:
            self.producer = Producer(conf)
            logger.info(f"Initialized Kafka producer for topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            self.producer = None

    def delivery_report(self, err, msg):
        """Called once for each message produced to indicate delivery result."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def send_job(self, job_id: str, audio_url: str, audio_id: str, client_policy: Optional[str] = None) -> bool:
        """
        Produce a job message to the Kafka topic.
        """
        if not self.producer:
            logger.error("Kafka producer not initialized, cannot send job")
            return False
            
        # Create message payload
        job_payload = {
            "job_id": job_id,
            "audio_url": audio_url,
            "audio_id": audio_id,
            "client_policy": client_policy,
            "timestamp": telemetry.get_current_timestamp() if hasattr(telemetry, 'get_current_timestamp') else None,
            "trace_id": telemetry.get_current_trace_id()
        }
        
        try:
            # Produce message
            self.producer.produce(
                self.topic,
                key=job_id,
                value=json.dumps(job_payload).encode('utf-8'),
                on_delivery=self.delivery_report,
                # Include trace ID in headers for distributed tracing
                headers=[("traceparent", telemetry.get_current_trace_id() or "")]
            )
            
            # Flush to ensure delivery for async jobs
            # In a high-volume system, we might not flush every time
            self.producer.poll(0)
            logger.info(f"Job {job_id} sent to Kafka topic {self.topic}")
            return True
            
        except Exception as e:
            logger.error(f"Error producing message to Kafka: {e}")
            telemetry.record_exception(e)
            return False

# Global instance
_producer_instance = None

def get_kafka_producer() -> KafkaProducer:
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = KafkaProducer()
    return _producer_instance
