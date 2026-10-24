package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.collaboration.TimeLogEntry;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public interface TimeLogRepository {
    List<TimeLogEntry> findByWorkItem(UUID workItemId);

    void insert(TimeLogEntry entry);

    BigDecimal sumHoursForWorkItem(UUID workItemId);
}
