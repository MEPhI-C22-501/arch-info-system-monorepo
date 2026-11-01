package ru.mephi.arch.tasktracker.application.workitem.support;

import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.domain.event.DomainEvent;

import java.util.ArrayList;
import java.util.List;

public class RecordingEventPublisher implements EventPublisherPort {
    public final List<DomainEvent> published = new ArrayList<>();
    @Override public void publish(DomainEvent event) { published.add(event); }

    public <T extends DomainEvent> List<T> ofType(Class<T> type) {
        return published.stream().filter(type::isInstance).map(type::cast).toList();
    }
}
