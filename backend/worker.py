import logging
import json
import signal
import sys
import time

from confluent_kafka import Consumer, KafkaException
from config import get_settings
from logic import ai_engine, cache, jobs
import telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

running = True

def shutdown(sig, frame):
    global running
    print("Shutdown signal received...")
    running = False

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)



settings=get_settings()

consumer=Consumer(settings.kafka_consumer)
consumer.subscribe(settings.kafka_topic)

print("\nConsuming messages...")
count=0

try:
    while running:
        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():
            raise KafkaException(msg.error())

        try:
            event = json.loads(msg.value().decode("utf-8"))
            audio_id = event["audio_id"]
            job_id = event["job_id"]
            audio_url = event["audio_url"]
            gcs_tag=event["gcs_tag"]
            client_policy=event["client_policy"]
            logger.info(f"Processing audio_id={audio_id}")

            if gcs_tag:
                ai_engine.analyse(gcs_uri,audio_id,client_policy)
            else:
                ai_engine.analyse(audio_url,audio_id,client_policy)

            
            print(f"Finished audio_id={audio_id}")

            # Commit only after success
            consumer.commit(msg)
            
            



        except Exception as e:
                    logger.error(f"Processing failed: {e}")
                    # Do NOT commit -> message will be retried

finally:
    logger.info("Closing consumer...")
    consumer.close()

