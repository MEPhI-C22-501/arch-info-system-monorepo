package ru.mephi.arch.tasktracker.domain.event;

import java.util.Map;
import java.util.UUID;

public record WorkItemFieldsChanged(UUID workItemId, String actorId, String source,
                                     Map<String, Object> oldValues, Map<String, Object> newValues)
    implements RecordableChange {
    @Override public String message() { return "Изменена карточка"; }
}
