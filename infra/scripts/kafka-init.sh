#!/bin/bash
# Генерирует локальные сертификат и конфиг Kafka. Повтор не перезаписывает keystore
# и не форматирует уже размеченный каталог данных.
set -euo pipefail

CERT_DIR=/var/lib/kafka/certs
DATA_DIR=/var/lib/kafka/data
CFG_DIR=/var/lib/kafka/config
CLUSTER_ID=5L6g3nShT-eMCtK--X86sw

: "${KAFKA_SSL_PASSWORD:?}"
: "${KAFKA_ADMIN_PASSWORD:?}"
: "${KAFKA_TASK_TRACKER_PASSWORD:?}"
: "${KAFKA_PLANNING_PASSWORD:?}"
: "${KAFKA_REPORTS_PASSWORD:?}"
: "${KAFKA_QA_PASSWORD:?}"
: "${KAFKA_REFERENCE_MANAGER_PASSWORD:?}"
: "${KAFKA_EXAMPLE_PASSWORD:?}"

mkdir -p "$CERT_DIR" "$DATA_DIR" "$CFG_DIR"

if [[ ! -f "$CERT_DIR/kafka.keystore.p12" ]]; then
  keytool -genkeypair -alias kafka -keyalg RSA -keysize 2048 -validity 825 \
    -storetype PKCS12 -keystore "$CERT_DIR/kafka.keystore.p12" \
    -storepass "$KAFKA_SSL_PASSWORD" -keypass "$KAFKA_SSL_PASSWORD" \
    -dname "CN=kafka" \
    -ext "SAN=dns:kafka,dns:localhost,ip:127.0.0.1"
  keytool -exportcert -alias kafka -rfc \
    -keystore "$CERT_DIR/kafka.keystore.p12" -storetype PKCS12 \
    -storepass "$KAFKA_SSL_PASSWORD" -file "$CERT_DIR/kafka.crt"
  keytool -importcert -alias kafka -noprompt \
    -file "$CERT_DIR/kafka.crt" \
    -keystore "$CERT_DIR/kafka.truststore.p12" -storetype PKCS12 \
    -storepass "$KAFKA_SSL_PASSWORD"
fi

jaas() {
  cat <<EOF
org.apache.kafka.common.security.plain.PlainLoginModule required username="admin" password="${KAFKA_ADMIN_PASSWORD}" user_admin="${KAFKA_ADMIN_PASSWORD}" user_task_tracker="${KAFKA_TASK_TRACKER_PASSWORD}" user_planning="${KAFKA_PLANNING_PASSWORD}" user_reports="${KAFKA_REPORTS_PASSWORD}" user_qa="${KAFKA_QA_PASSWORD}" user_reference_manager="${KAFKA_REFERENCE_MANAGER_PASSWORD}" user_example="${KAFKA_EXAMPLE_PASSWORD}";
EOF
}

JAAS_VALUE="$(jaas)"

cat > "$CFG_DIR/server.properties" <<EOF
process.roles=broker,controller
node.id=1
controller.quorum.voters=1@kafka:9093
controller.listener.names=CONTROLLER
listeners=INTERNAL://0.0.0.0:9092,EXTERNAL://0.0.0.0:29092,CONTROLLER://0.0.0.0:9093
advertised.listeners=INTERNAL://kafka:9092,EXTERNAL://localhost:29092
listener.security.protocol.map=INTERNAL:SASL_SSL,EXTERNAL:SASL_SSL,CONTROLLER:PLAINTEXT
inter.broker.listener.name=INTERNAL
sasl.enabled.mechanisms=PLAIN
sasl.mechanism.inter.broker.protocol=PLAIN
listener.name.internal.plain.sasl.jaas.config=${JAAS_VALUE}
listener.name.external.plain.sasl.jaas.config=${JAAS_VALUE}
ssl.keystore.type=PKCS12
ssl.keystore.location=${CERT_DIR}/kafka.keystore.p12
ssl.keystore.password=${KAFKA_SSL_PASSWORD}
ssl.key.password=${KAFKA_SSL_PASSWORD}
ssl.truststore.type=PKCS12
ssl.truststore.location=${CERT_DIR}/kafka.truststore.p12
ssl.truststore.password=${KAFKA_SSL_PASSWORD}
ssl.client.auth=none
ssl.endpoint.identification.algorithm=HTTPS
authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer
allow.everyone.if.no.acl.found=false
super.users=User:admin;User:ANONYMOUS
auto.create.topics.enable=false
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
group.initial.rebalance.delay.ms=0
num.partitions=1
log.retention.hours=168
log.dirs=${DATA_DIR}
EOF

cat > "$CFG_DIR/admin.properties" <<EOF
security.protocol=SASL_SSL
sasl.mechanism=PLAIN
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="admin" password="${KAFKA_ADMIN_PASSWORD}";
ssl.truststore.type=PKCS12
ssl.truststore.location=${CERT_DIR}/kafka.truststore.p12
ssl.truststore.password=${KAFKA_SSL_PASSWORD}
ssl.endpoint.identification.algorithm=HTTPS
EOF

chown -R 1000:1000 "$CERT_DIR" "$DATA_DIR" "$CFG_DIR"
chmod 750 "$CERT_DIR" "$CFG_DIR"
chmod 640 "$CERT_DIR"/kafka.keystore.p12 "$CERT_DIR"/kafka.truststore.p12 "$CFG_DIR"/*.properties
chmod 644 "$CERT_DIR/kafka.crt"

/opt/kafka/bin/kafka-storage.sh format \
  --config "$CFG_DIR/server.properties" \
  --cluster-id "$CLUSTER_ID" \
  --ignore-formatted
chown -R 1000:1000 "$DATA_DIR"
