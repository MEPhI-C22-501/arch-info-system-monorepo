package ru.mephi.arch.tasktracker.application.port;

import java.util.UUID;

public interface StatusRepository {
    boolean isActive(UUID id);

    /** First active status in board order, category OPEN — the default a new item gets. */
    UUID defaultStatusId();

    StatusSummary findSummary(UUID id);

    record StatusSummary(String name, String category) {}
}
