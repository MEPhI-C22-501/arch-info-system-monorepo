package ru.mephi.arch.tasktracker.domain.event;

import java.util.Map;
import java.util.UUID;

public record WorkItemCreated(UUID workItemId, String actorId, String source, Map<String, Object> newValues)
    implements RecordableChange {
    @Override public Map<String, Object> oldValues() { return Map.of(); }
    @Override public String message() { return "Создан рабочий элемент"; }
}
