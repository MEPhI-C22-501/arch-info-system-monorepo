package ru.mephi.arch.tasktracker.domain.event;

import java.util.Map;
import java.util.UUID;

public record AttachmentChanged(UUID workItemId, String actorId, String source,
                                 Map<String, Object> oldValues, Map<String, Object> newValues, String message)
    implements RecordableChange {
}
