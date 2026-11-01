package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.TimeLogRepository;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.collaboration.TimeLogEntry;
import ru.mephi.arch.tasktracker.domain.event.TimeLogged;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

@Service
public class LogTime {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final TimeLogRepository timeLogs;
    private final EventPublisherPort events;
    public LogTime(WorkItemRepository workItems, PermissionPort permissions, TimeLogRepository timeLogs, EventPublisherPort events) {
        this.workItems = workItems; this.permissions = permissions; this.timeLogs = timeLogs; this.events = events;
    }

    @Transactional
    public Map<String, Object> execute(UUID workItemId, Map<String, Object> body) {
        var item = workItems.getById(workItemId);
        permissions.requireItemReadable(item.assigneeId);
        permissions.require("time.create");
        if (workItems.hasChildren(workItemId) || Set.of(WorkItemType.PROJECT, WorkItemType.EPIC).contains(item.type)) {
            throw ApiException.invalid("workItemId", "time_only_for_leaf");
        }
        BigDecimal hours = Values.hours(body.get("hours"), "hours", true);
        if (hours == null) throw ApiException.invalid("hours", "required");
        LocalDate date = Values.date(body.get("loggedDate"), "loggedDate");
        if (date == null) throw ApiException.invalid("loggedDate", "required");
        UUID id = UUID.randomUUID();
        String note = Objects.toString(body.get("comment"), "");
        String actor = permissions.currentSubject();
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        timeLogs.insert(new TimeLogEntry(id, workItemId, actor, date, hours, note, now));
        workItems.touch(workItemId);
        events.publish(new TimeLogged(workItemId, actor, null, Map.of("timeLogAdded", false),
            Map.of("timeLogAdded", id.toString()), "Зарегистрировано время"));
        return Map.of("id", id, "hours", hours, "loggedDate", date, "comment", note, "userId", actor);
    }
}
