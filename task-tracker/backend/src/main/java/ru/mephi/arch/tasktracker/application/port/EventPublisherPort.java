package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.event.DomainEvent;

public interface EventPublisherPort {
    void publish(DomainEvent event);
}
