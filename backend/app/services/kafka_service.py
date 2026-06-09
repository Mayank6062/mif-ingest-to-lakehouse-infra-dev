"""
Kafka + Schema Registry service — validates topic existence and schema presence.

Uses kafka-python (KafkaAdminClient) for broker topic listing and httpx for
Schema Registry REST API calls.  Both are synchronous — safe to call from
LangGraph node functions (which are sync).

All methods return structured results and NEVER raise.  Callers receive
error flags rather than exceptions so the workflow can decide how to proceed.

Schema matching rule:
    subject.startswith(topic + "-")

Example:
    topic   = "dev.saptcc.multi-1.raw"
    subject = "dev.saptcc.multi-1.raw-obj_1"  ← match ✓
    subject = "dev.saptcc.multi-1.raw-value"  ← match ✓
    subject = "dev.saptcc.multi-1"            ← no match ✗
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


class KafkaService:
    """
    Validates Kafka topic existence and Schema Registry schema presence.

    Both checks are independent — a failure in one does not affect the other.
    Instantiate per-request (stateless; clients are created and closed inline).
    """

    # ── Kafka topic check ─────────────────────────────────────────────────────

    def check_topic_exists(self, topic: str) -> tuple[bool, str | None]:
        """
        Check whether *topic* exists in the Kafka broker.

        Returns:
            (True,  None)       — topic found in broker
            (False, None)       — broker reachable but topic absent
            (False, error_str)  — broker unreachable / timeout / error
        """
        settings = get_settings()
        try:
            try:
                from kafka.admin import KafkaAdminClient  # imported lazily so tests can patch
            except Exception as ie:
                # Some kafka-python builds attempt to import vendored `six` as
                # `kafka.vendor.six.moves` which may not exist in the environment.
                # Provide a compatibility shim by aliasing the installed `six`
                # into `kafka.vendor.six` and `kafka.vendor.six.moves` then retry.
                try:
                    import sys
                    import types
                    import six

                    pkg = types.ModuleType("kafka.vendor")
                    sys.modules.setdefault("kafka.vendor", pkg)
                    # six is a module; expose it under the vendored name
                    sys.modules["kafka.vendor.six"] = six
                    sys.modules["kafka.vendor.six.moves"] = six.moves
                except Exception:
                    # If shim fails, re-raise the original import error
                    raise ie

                # Retry import after shim
                from kafka.admin import KafkaAdminClient

            admin = KafkaAdminClient(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                request_timeout_ms=settings.kafka_admin_timeout_seconds * 1000,
                client_id="mif-glue-job-creator",
            )
            try:
                topics = admin.list_topics()
                exists = topic in topics
                logger.debug(
                    "Kafka topic check: topic=%s exists=%s broker=%s",
                    topic,
                    exists,
                    settings.kafka_bootstrap_servers,
                )
                return exists, None
            finally:
                try:
                    admin.close()
                except Exception:
                    pass  # best-effort close
        except Exception as exc:
            logger.warning(
                "Kafka admin check failed: broker=%s error=%s — trying consumer fallback",
                settings.kafka_bootstrap_servers,
                exc,
            )
            # Fallback: try KafkaConsumer.topics() which may succeed when admin client
            # metadata path is blocked but consumer can fetch topics.
            try:
                from kafka import KafkaConsumer

                consumer = KafkaConsumer(
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    request_timeout_ms=max(1000, settings.kafka_admin_timeout_seconds * 1000),
                    client_id="mif-glue-job-consumer-fallback",
                )
                try:
                    topics = consumer.topics()
                    exists = topic in topics
                    logger.debug(
                        "Kafka consumer fallback: topic=%s exists=%s broker=%s",
                        topic,
                        exists,
                        settings.kafka_bootstrap_servers,
                    )
                    return exists, None
                finally:
                    try:
                        consumer.close()
                    except Exception:
                        pass
            except Exception as exc2:
                logger.warning(
                    "Kafka consumer fallback failed: broker=%s error=%s",
                    settings.kafka_bootstrap_servers,
                    exc2,
                )
                return False, f"{exc} | fallback: {exc2}"

    # ── Schema Registry subject check ─────────────────────────────────────────

    def get_schema_count(self, topic: str) -> tuple[bool, int, str | None]:
        """
        Fetch all Schema Registry subjects and count those matching *topic*
        using prefix matching: subject.startswith(topic + "-").

        Returns:
            (True,  count, None)       — SR reachable; count is valid (may be 0)
            (False, 0,     error_str)  — SR unreachable / timeout / non-200 response
        """
        settings = get_settings()
        url = f"{settings.schema_registry_url.rstrip('/')}/subjects"
        try:
            import httpx  # already in requirements; imported lazily for easier mocking

            response = httpx.get(url, timeout=settings.schema_registry_timeout_seconds)
            response.raise_for_status()
            all_subjects: list[str] = response.json()

            prefix = topic + "-"
            matching = [s for s in all_subjects if s.startswith(prefix)]
            count = len(matching)

            logger.debug(
                "Schema Registry check: topic=%s sr_url=%s total_subjects=%d matching=%d",
                topic,
                url,
                len(all_subjects),
                count,
            )
            return True, count, None

        except Exception as exc:
            logger.warning(
                "Schema Registry check failed: url=%s error=%s",
                url,
                exc,
            )
            return False, 0, str(exc)
