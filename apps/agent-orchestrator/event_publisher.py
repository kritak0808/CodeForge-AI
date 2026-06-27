import json
import logging
import time
import threading
from typing import Any, Dict, Callable, Optional

try:
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.errors import KafkaError
except ImportError:
    KafkaProducer = None
    KafkaConsumer = None
    KafkaError = Exception

logger = logging.getLogger("agent-orchestrator.event-publisher")

_local_listeners = {}
_listeners_lock = threading.Lock()

class KafkaEventPublisher:
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.offline_mode = False
        
        import os
        if os.getenv("KAFKA_DISABLED", "false").lower() == "true":
            logger.warning("KAFKA_DISABLED is true — falling back to offline/logger-only mode.")
            self.producer = None
            self.offline_mode = True
            return

        if not KafkaProducer:
            logger.warning("Kafka libraries not available — falling back to offline/logger-only mode.")
            self.producer = None
            self.offline_mode = True
            return

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=2000,
                max_block_ms=2000,
                retries=1,
                connections_max_idle_ms=5000,
            )
            logger.info("Kafka Producer initialized successfully.")
        except Exception as e:
            logger.warning(f"Kafka unavailable (falling back to offline/logger-only mode): {e}")
            self.producer = None
            self.offline_mode = True

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Publishes a message to the specified Kafka topic.
        """
        logger.info(f"[Kafka Event Publish] Topic: {topic} | Payload: {json.dumps(payload)}")
        if self.offline_mode or not self.producer:
            # Dispatch locally asynchronously to mimic decoupled event broker execution
            def local_dispatch():
                with _listeners_lock:
                    listeners = list(_local_listeners.get(topic, []))
                if listeners:
                    logger.info(f"[Local Event Dispatch] Routing to {len(listeners)} listeners for topic '{topic}'")
                    for listener in listeners:
                        try:
                            cloned = json.loads(json.dumps(payload))
                            listener(cloned)
                        except Exception as e:
                            logger.error(f"Error executing local listener for topic {topic}: {e}")
                else:
                    logger.debug(f"[Local Event Dispatch] No local listeners registered for topic '{topic}'")
            
            threading.Thread(target=local_dispatch, daemon=True).start()
            return False

        try:
            future = self.producer.send(topic, value=payload)
            future.get(timeout=1.0)
            return True
        except KafkaError as ke:
            logger.error(f"Kafka publishing error on topic {topic}: {ke}")
            return False
        except Exception as e:
            logger.error(f"Generic error publishing event to topic {topic}: {e}")
            return False

    def retry(self, topic: str, payload: Dict[str, Any], attempt: int = 1, max_attempts: int = 3) -> bool:
        """
        Retries publishing a message with backoff. If max_attempts reached, routes to dead letter.
        """
        try:
            success = self.publish(topic, payload)
            if success:
                return True
            if attempt < max_attempts:
                backoff = 2 ** attempt
                logger.warning(f"Retry attempt {attempt} for topic {topic} failed. Waiting {backoff}s...")
                time.sleep(backoff)
                return self.retry(topic, payload, attempt + 1, max_attempts)
            else:
                logger.error(f"Failed to publish event after {max_attempts} attempts. Routing to DLQ.")
                self.dead_letter(topic, payload, "Max publish attempts exceeded")
                return False
        except Exception as e:
            logger.error(f"Error during retry sequence: {e}")
            self.dead_letter(topic, payload, str(e))
            return False

    def dead_letter(self, original_topic: str, payload: Dict[str, Any], reason: str) -> bool:
        """
        Routes failed messages to the dead-letter queue (workflow.errors or dlq topic).
        """
        dlq_payload = {
            "original_topic": original_topic,
            "original_payload": payload,
            "failed_at": time.time(),
            "reason": reason
        }
        logger.error(f"[DLQ Event] Routing failed event to workflow.errors. Reason: {reason}")
        return self.publish("workflow.errors", dlq_payload)

    def start_consumer(self, topic: str, group_id: str, callback: Callable[[Dict[str, Any]], None], stop_check: Optional[Callable[[], bool]] = None):
        """
        Starts a block consumer loop on a topic (to be run in background thread or process).
        """
        if self.offline_mode:
            logger.warning(f"Kafka in offline mode. Registering local consumer for topic {topic}")
            topics = [topic] if isinstance(topic, str) else list(topic)
            with _listeners_lock:
                for t in topics:
                    if t not in _local_listeners:
                        _local_listeners[t] = []
                    _local_listeners[t].append(callback)
            
            while True:
                if stop_check and stop_check():
                    logger.info(f"Stopping local consumer for topic {topic} due to stop check.")
                    break
                time.sleep(1)
            return

        try:
            topics = [topic] if isinstance(topic, str) else list(topic)
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                consumer_timeout_ms=1000
            )
            logger.info(f"Started Kafka consumer for topic '{topic}' in group '{group_id}'")
            
            while True:
                if stop_check and stop_check():
                    logger.info(f"Stopping consumer for topic {topic} due to stop check.")
                    break
                for message in consumer:
                    try:
                        callback(message.value)
                    except Exception as cb_err:
                        logger.error(f"Error executing consumer callback: {cb_err}")
                        self.dead_letter(topic, message.value, f"Callback error: {cb_err}")
        except Exception as e:
            logger.warning(f"Kafka consumer for topic '{topic}' failed to start or terminated: {e}")

