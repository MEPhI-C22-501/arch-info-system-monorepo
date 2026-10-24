package ru.mephi.arch.tasktracker.infrastructure.event;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.domain.event.DomainEvent;

/** One-line delegation to Spring's own publisher — plain {@code @EventListener}s run synchronously,
 * inline, in the same thread and transaction as the publishing use case (ADR-007). Never add
 * {@code @TransactionalEventListener(phase = AFTER_COMMIT)} listeners for these events — that would
 * move the audit/notification side effect outside the transaction, which ADR-007 explicitly rejects. */
@Component
public class SpringDomainEventPublisher implements EventPublisherPort {
    private final ApplicationEventPublisher delegate;
    public SpringDomainEventPublisher(ApplicationEventPublisher delegate) { this.delegate = delegate; }

    @Override public void publish(DomainEvent event) { delegate.publishEvent(event); }
}
