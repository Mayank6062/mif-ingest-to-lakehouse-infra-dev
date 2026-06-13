locals {
  saptce_multi_nonpii_raw_topics = {
    "multi-1"      = 3,
    "multi-3"      = 3,
  }
 
  saptce_multi_pii_raw_topics = {
    "multi-2" = 3,
  }
 
  saptce_slt_1_to_1_pii_raw_topic = {
  }

  saptce_slt_1_to_1_nonpii_raw_topic = {
  }
}
 
module "saptce_slt_1_to_1_pii_raw_topic" {
  source   = "./modules/minerva_cc_topic"
  for_each = local.saptce_slt_1_to_1_pii_raw_topic
  kafka_cluster           = data.confluent_kafka_cluster.dedicated
  schema_registry_cluster = data.confluent_schema_registry_cluster.dedicated
  environment   = local.env
  source_system = "saptce"
  schema_grain  = each.key
  data_state    = "raw"ac
  schema_format = "JSON"
  encrypt_tags = [confluent_tag.pii.name]
  minerva_tags = {
    "DataClassification" = local.classification_confidential_restricted
  }
  config = {
    "cleanup.policy"                        = "delete"
    "retention.ms"                          = "-1"
    "confluent.key.schema.validation"       = false
    "confluent.value.schema.validation"     = false
    "confluent.value.subject.name.strategy" = "io.confluent.kafka.serializers.subject.TopicRecordNameStrategy"
  }
  generate_key_schema   = false
  generate_value_schema = false
}
 
module "saptce_slt_1_to_1_nonpii_raw_topic" {
  source   = "./modules/minerva_cc_topic"
  for_each = local.saptce_slt_1_to_1_nonpii_raw_topic
  kafka_cluster           = data.confluent_kafka_cluster.dedicated
  schema_registry_cluster = data.confluent_schema_registry_cluster.dedicated
  environment   = local.env
  source_system = "saptce"
  schema_grain  = each.key
  data_state    = "raw"
  schema_format = "JSON"
  config = {
    "cleanup.policy"                        = "delete"
    "retention.ms"                          = "-1"
    "confluent.key.schema.validation"       = false
    "confluent.value.schema.validation"     = false
    "confluent.value.subject.name.strategy" = "io.confluent.kafka.serializers.subject.TopicRecordNameStrategy"
  }
  generate_key_schema   = false
  generate_value_schema = false
}

module "saptce_pii_raw_topic" {
  for_each = local.saptce_pii_slt_raw
  source   = "./modules/minerva_cc_topic"
  kafka_cluster           = data.confluent_kafka_cluster.dedicated
  schema_registry_cluster = data.confluent_schema_registry_cluster.dedicated
  environment   = local.env
  source_system = "saptce"
  schema_grain  = each.key
  data_state    = "raw"
  schema_format = "JSON"
  encrypt_tags = [confluent_tag.pii.name]
  minerva_tags = {
    "DataClassification" = local.classification_confidential_limited
  }
  config = contains(local.tce_data_deletion_topics, each.key) ? local.tce_raw_topic_config_override : {
    "cleanup.policy"                    = "delete"
    "retention.ms"                      = "-1"
    "confluent.key.schema.validation"   = false
    "confluent.value.schema.validation" = false
  }
  generate_key_schema   = false
  generate_value_schema = false
}
 
module "saptce_multi_nonpii_raw_topics" {
  source   = "./modules/minerva_cc_topic"
  for_each = local.saptce_multi_nonpii_raw_topics
  kafka_cluster           = data.confluent_kafka_cluster.dedicated
  schema_registry_cluster = data.confluent_schema_registry_cluster.dedicated
  environment   = local.env
  source_system = "saptce"
  schema_grain  = each.key
  data_state    = "raw"
  schema_format = "JSON"
  config = contains(local.tce_retention_14days_objs, each.key) ? local.tce_topic_14days_retention_config_override : {
    "cleanup.policy"                        = "delete"
    "retention.ms"                          = "-1"
    "confluent.key.schema.validation"       = false
    "confluent.value.schema.validation"     = false
    "confluent.key.subject.name.strategy"   = "io.confluent.kafka.serializers.subject.TopicNameStrategy"
    "confluent.value.subject.name.strategy" = "io.confluent.kafka.serializers.subject.TopicRecordNameStrategy"
  }
  generate_key_schema   = false
  generate_value_schema = false
  partitions_count = each.value
}
 
module "saptce_multi_pii_raw_topics" {
  source   = "./modules/minerva_cc_topic"
  for_each = local.saptce_multi_pii_raw_topics
  kafka_cluster           = data.confluent_kafka_cluster.dedicated
  schema_registry_cluster = data.confluent_schema_registry_cluster.dedicated
  environment   = local.env
  source_system = "saptce"
  schema_grain  = each.key
  data_state    = "raw"
  schema_format = "JSON"
  minerva_tags = {
    "DataClassification" = local.classification_confidential_restricted
  }
  config = contains(local.tce_retention_14days_objs, each.key) ? local.tce_topic_14days_retention_config_override : {
    "cleanup.policy"                        = "delete"
    "retention.ms"                          = "-1"
    "confluent.key.schema.validation"       = false
    "confluent.value.schema.validation"     = true
    "confluent.key.subject.name.strategy"   = "io.confluent.kafka.serializers.subject.TopicNameStrategy"
    "confluent.value.subject.name.strategy" = "io.confluent.kafka.serializers.subject.TopicRecordNameStrategy"
  }
  generate_key_schema   = false
  generate_value_schema = false
  partitions_count = each.value
}
 