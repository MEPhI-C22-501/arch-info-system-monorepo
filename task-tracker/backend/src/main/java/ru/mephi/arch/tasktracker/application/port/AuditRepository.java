package ru.mephi.arch.tasktracker.application.port;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public interface AuditRepository {
    void record(UUID workItemId, String actorId, String source, OffsetDateTime occurredAt,
                List<String> changedFields, Map<String, Object> oldValues, Map<String, Object> newValues);

    List<Map<String, Object>> findByWorkItem(UUID workItemId);
}
