package ru.mephi.arch.tasktracker.infrastructure.event;

import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import ru.mephi.arch.tasktracker.application.port.AuditRepository;
import ru.mephi.arch.tasktracker.domain.event.RecordableChange;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** Diffs {@code oldValues}/{@code newValues} down to only the changed keys and records them —
 * exactly what {@code ChangeRecorder.record} used to do inline, now driven by the event instead. */
@Component
public class AuditEventListener {
    private final AuditRepository audit;
    public AuditEventListener(AuditRepository audit) { this.audit = audit; }

    @EventListener
    public void on(RecordableChange event) {
        Map<String, Object> oldDiff = new LinkedHashMap<>();
        Map<String, Object> newDiff = new LinkedHashMap<>();
        List<String> changedFields = new ArrayList<>();
        for (String key : event.newValues().keySet()) {
            if (!Objects.equals(event.oldValues().get(key), event.newValues().get(key))) {
                changedFields.add(key);
                oldDiff.put(key, event.oldValues().get(key));
                newDiff.put(key, event.newValues().get(key));
            }
        }
        if (changedFields.isEmpty()) return;
        audit.record(event.workItemId(), event.actorId(), event.source(), OffsetDateTime.now(ZoneOffset.UTC),
            changedFields, oldDiff, newDiff);
    }
}
