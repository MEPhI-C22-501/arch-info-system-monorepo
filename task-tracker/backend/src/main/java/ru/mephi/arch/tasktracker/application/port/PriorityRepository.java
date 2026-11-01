package ru.mephi.arch.tasktracker.application.port;

import java.util.UUID;

public interface PriorityRepository {
    boolean isActive(UUID id);

    /** First active priority in sort order — the default a new item gets. */
    UUID defaultPriorityId();
}
