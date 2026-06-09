import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.kafka_service import KafkaService

s = KafkaService()

topic = 'dev.saptcc.multi-1.raw'
exists, err = s.check_topic_exists(topic)
print('topic_exists=', exists, 'error=', err)

sr_ok, count, sr_err = s.get_schema_count(topic)
print('schema_registry_ok=', sr_ok, 'schema_count=', count, 'error=', sr_err)
