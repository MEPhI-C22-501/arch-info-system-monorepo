package ru.mephi.arch.tasktracker.domain.collaboration;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

public final class TimeLogEntry {
    public final UUID id;
    public final UUID workItemId;
    public final String externalUserId;
    public final LocalDate loggedDate;
    public final BigDecimal hours;
    public final String comment;
    public final OffsetDateTime createdAt;

    public TimeLogEntry(UUID id, UUID workItemId, String externalUserId, LocalDate loggedDate, BigDecimal hours,
                         String comment, OffsetDateTime createdAt) {
        this.id = id; this.workItemId = workItemId; this.externalUserId = externalUserId;
        this.loggedDate = loggedDate; this.hours = hours; this.comment = comment; this.createdAt = createdAt;
    }
}
