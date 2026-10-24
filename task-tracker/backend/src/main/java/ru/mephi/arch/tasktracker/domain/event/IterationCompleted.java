package ru.mephi.arch.tasktracker.domain.event;

import java.util.UUID;

/** Same note as {@link IterationActivated}: no listener wired, matching the old no-audit behavior. */
public record IterationCompleted(UUID iterationId, String actorId) implements DomainEvent {
}
