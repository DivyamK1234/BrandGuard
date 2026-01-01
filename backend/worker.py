import asyncio
import json
import logging
import signal

from confluent_kafka import Consumer, KafkaException
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from config import get_settings
from logic import ai_engine
import telemetry

# Initialize OpenTelemetry before any processing
telemetry.setup_telemetry()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

running = True


def shutdown(sig, frame):
    global running
    logger.info("Shutdown signal received...")
    running = False


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


async def consume():
    global running

    settings = get_settings()
    consumer = Consumer(settings.kafka_consumer)
    consumer.subscribe(["audio-verification-non-url"])

    logger.info("Consuming messages...")

    try:
        while running:
            msg = consumer.poll(1.0)

            if msg is None:
                await asyncio.sleep(0)  # yield control
                continue

            if msg.error():
                continue
                # raise KafkaException(msg.error())

            try:
                event = json.loads(msg.value().decode("utf-8"))

                audio_id = event["audio_id"]
                audio_url = event["audio_url"]
                job_id = event["job_id"]
                gcs_tag = event.get("gcs_tag")
                client_policy = event.get("client_policy")

                # Extract trace context from Kafka headers
                headers = {h[0]: h[1].decode() for h in (msg.headers() or [])}
                propagator = TraceContextTextMapPropagator()
                ctx = propagator.extract(headers)

                # Create span with parent context from the original request
                tracer = telemetry.get_tracer()
                with tracer.start_as_current_span("worker.process_audio", context=ctx) as span:
                    span.set_attribute("audio_id", audio_id)
                    span.set_attribute("job_id", job_id)
                    span.set_attribute("gcs_tag", gcs_tag or "unknown")

                    logger.info(f"Processing audio_id={audio_id}, job_id={job_id}")

                    if gcs_tag == "1":
                        result = await ai_engine.analyze(
                            gcs_uri=audio_url,
                            audio_id=audio_id,
                            client_policy=client_policy,
                        )
                        if hasattr(result, 'model_dump'):
                            result_dict = result.model_dump(mode='json')
                        else:
                            # Manually serialize datetime fields
                            result_dict = {}
                            for key, value in result.__dict__.items():
                                if isinstance(value, datetime):
                                    result_dict[key] = value.isoformat()
                                elif hasattr(value, 'value'):  # Enum
                                    result_dict[key] = value.value
                                else:
                                    result_dict[key] = value
                        from logic.jobs import get_job_queue, JobStatus
                        queue = get_job_queue()
                        queue.update_job(
                            job_id=job_id,
                            status=JobStatus.COMPLETE,
                            progress=100,
                            message="Analysis complete!",
                            result=result_dict,
                            error=None
                        )
                        
                        logger.info(f"Result: {result}")
                        from logic.cache import set_cache
                        set_cache(audio_id, result)

                    else:
                        from logic.jobs import process_url_job
                        logger.info(f"Processing URL audio_id={audio_id}")
                        await process_url_job(job_id, audio_url, audio_id, client_policy)
                       
                    logger.info(f"Finished audio_id={audio_id}")

                # Commit ONLY after successful processing
                consumer.commit(msg) 

            except Exception as e:
                logger.exception(f"Processing failed for audio_id={audio_id}")
                # ❌ do NOT commit → Kafka will retry

    finally:
        logger.info("Closing Kafka consumer...")
        consumer.close()


if __name__ == "__main__":
    asyncio.run(consume())
