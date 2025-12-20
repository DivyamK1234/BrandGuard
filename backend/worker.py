import json
import asyncio
import logging
import signal
import sys
from confluent_kafka import Consumer, KafkaError

from config import get_settings
from logic.jobs import get_job_queue, JobStatus, process_url_job
import telemetry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("brandguard-worker")

class BrandGuardWorker:
    """
    Kafka Consumer Worker for BrandGuard.
    Processes audio verification jobs from Kafka topic.
    """
    
    def __init__(self):
        settings = get_settings()
        self.topic = settings.kafka_topic_jobs
        
        # Consumer configuration
        conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'group.id': 'brandguard-worker-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False  # Manual commit for better reliability
        }
        
        try:
            self.consumer = Consumer(conf)
            self.consumer.subscribe([self.topic])
            logger.info(f"Worker subscribed to topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            sys.exit(1)
            
        self.running = True

    def stop(self):
        """Stop the consumer loop."""
        self.running = False

    async def run(self):
        """Main worker loop."""
        logger.info("BrandGuard Worker started and waiting for jobs...")
        
        # Initialize telemetry
        telemetry.setup_telemetry()
        
        try:
            while self.running:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    elif msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                        logger.warning(f"Topic {self.topic} not created yet. Waiting...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        break

                # Process message
                try:
                    payload = json.loads(msg.value().decode('utf-8'))
                    job_id = payload.get('job_id')
                    audio_url = payload.get('audio_url')
                    audio_id = payload.get('audio_id')
                    client_policy = payload.get('client_policy')
                    
                    logger.info(f"Received job: {job_id} for audio: {audio_id}")
                    
                    # Process the job using existing logic
                    # This already updates Redis status
                    await process_url_job(
                        job_id=job_id,
                        audio_url=audio_url,
                        audio_id=audio_id,
                        client_policy=client_policy
                    )
                    
                    # Commit offset after successful processing
                    self.consumer.commit(asynchronous=False)
                    logger.info(f"Successfully processed and committed job: {job_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing job from Kafka: {e}")
                    # Depending on policy, we might still commit to avoid infinite loops
                    # or keep retrying if it's a transient error.
                    # For now, we log and commit to avoid getting stuck.
                    self.consumer.commit(asynchronous=False)
                    
        finally:
            # Shutdown
            logger.info("Shutting down worker...")
            self.consumer.close()
            telemetry.shutdown_telemetry()

if __name__ == "__main__":
    worker = BrandGuardWorker()
    
    # Handle termination signals
    def handle_exit(sig, frame):
        logger.info("Shutdown signal received")
        worker.stop()
        
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # Run the async loop
    asyncio.run(worker.run())
