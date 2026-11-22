package ru.mephi.arch.tasktracker;

import org.apache.kafka.clients.producer.KafkaProducer;
import org.junit.jupiter.api.Test;
import java.util.Properties;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OutboxConfigurationTest {
    @Test void supportsBothTheInfrastructurePlainMechanismAndExplicitScram() {
        for (String mechanism : new String[] {"PLAIN", "SCRAM-SHA-512"}) {
            try (var ignored = mockConstruction(KafkaProducer.class, (mock, context) -> {
                var properties = (Properties) context.arguments().getFirst();
                assertEquals(mechanism, properties.get("sasl.mechanism"));
                assertEquals("SASL_SSL", properties.get("security.protocol"));
                assertEquals("test-jaas", properties.get("sasl.jaas.config"));
            })) {
                new Outbox(null, "broker:9092", "SASL_SSL", "test-jaas", "", "", mechanism).close();
                assertEquals(1, ignored.constructed().size());
            }
        }
    }
}
