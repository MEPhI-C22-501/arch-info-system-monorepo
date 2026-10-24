package ru.mephi.arch.tasktracker.domain.event;

import java.util.UUID;

/**
 * Deliberately NOT a {@link RecordableChange} and deliberately unsubscribed today — the old
 * IterationService.activate() never wrote an audit entry or a notification, only the
 * baseline_snapshot column. Wiring a listener here would be a real, new behavior change, not a
 * faithful port — see the backend restructuring plan.
 */
public record IterationActivated(UUID iterationId, String actorId) implements DomainEvent {
}
