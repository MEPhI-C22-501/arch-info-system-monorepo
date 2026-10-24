package ru.mephi.arch.tasktracker.domain.iteration;

import ru.mephi.arch.tasktracker.ApiException;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

public final class Iteration {
    public final UUID id;
    public String name;
    public String description;
    public LocalDate startDate;
    public LocalDate endDate;
    public IterationState state;
    public final OffsetDateTime createdAt;

    public Iteration(UUID id, String name, String description, LocalDate startDate, LocalDate endDate,
                      IterationState state, OffsetDateTime createdAt) {
        this.id = id; this.name = name; this.description = description;
        this.startDate = startDate; this.endDate = endDate; this.state = state; this.createdAt = createdAt;
    }

    /** Mirrors the old editable() guard — mutating a completed iteration is always rejected. */
    public void ensureEditable() {
        if (state == IterationState.COMPLETED) throw ApiException.conflict("iteration", "completed");
    }
}
