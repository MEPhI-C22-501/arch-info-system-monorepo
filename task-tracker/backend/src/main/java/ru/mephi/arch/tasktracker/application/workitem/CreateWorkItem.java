package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.domain.event.HierarchyChanged;
import ru.mephi.arch.tasktracker.domain.event.WorkItemCreated;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemFactory;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/**
 * No {@code item.create} permission check in here on purpose — this is also meant to be reused by
 * the (not-yet-migrated) Excel import and testing-service bug-creation paths, which intentionally
 * bypass it; the plain human-facing controller checks the permission itself before calling this.
 */
@Service
public class CreateWorkItem {
    private final WorkItemRepository workItems;
    private final StatusRepository statuses;
    private final PriorityRepository priorities;
    private final TypeSettingRepository typeSettings;
    private final UserDirectoryRepository directory;
    private final PermissionPort permissions;
    private final EventPublisherPort events;
    private final ViewWorkItem view;

    public CreateWorkItem(WorkItemRepository workItems, StatusRepository statuses, PriorityRepository priorities,
                           TypeSettingRepository typeSettings, UserDirectoryRepository directory,
                           PermissionPort permissions, EventPublisherPort events, ViewWorkItem view) {
        this.workItems = workItems; this.statuses = statuses; this.priorities = priorities;
        this.typeSettings = typeSettings; this.directory = directory; this.permissions = permissions;
        this.events = events; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(Map<String, Object> input, String actor, String source) {
        WorkItemType type = WorkItemType.from(Values.str(input, "type", true));
        if (!typeSettings.isEnabled(type)) throw ApiException.invalid("type", "disabled");
        String title = Values.str(input, "title", true);

        UUID statusId = Values.uuid(input.getOrDefault("statusId", statuses.defaultStatusId()), "statusId");
        if (!statuses.isActive(statusId)) throw ApiException.invalid("statusId", "unknown_or_inactive");
        UUID priorityId = Values.uuid(input.getOrDefault("priorityId", priorities.defaultPriorityId()), "priorityId");
        if (!priorities.isActive(priorityId)) throw ApiException.invalid("priorityId", "unknown_or_inactive");

        UUID parentId = Values.uuid(input.get("parentId"), "parentId");
        UUID id = input.get("id") == null ? UUID.randomUUID() : Values.uuid(input.get("id"), "id");
        WorkItem parent = parentId == null ? null : workItems.getById(parentId);

        String assignee = nullableString(input.get("assigneeId"));
        if (source == null && "MEMBER".equals(permissions.currentRole()) && assignee == null) assignee = actor;
        if (assignee != null && !directory.isActive(assignee)) throw ApiException.invalid("assigneeId", "unknown_or_inactive");

        LocalDate start = Values.date(input.get("startDate"), "startDate");
        LocalDate due = Values.date(input.get("dueDate"), "dueDate");
        BigDecimal planned = Values.hours(input.get("plannedHours"), "plannedHours", false);
        String description = Objects.toString(input.getOrDefault("description", ""), "");
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);

        WorkItem item = WorkItemFactory.create(id, type, title, description, statusId, priorityId, assignee,
            start, due, planned, parentId, parent,
            (String) input.get("externalSource"), (String) input.get("externalDefectId"), (String) input.get("severity"),
            Objects.toString(input.getOrDefault("environment", null), null),
            (String) input.get("testRunUrl"), (String) input.get("testCaseUrl"), now);
        workItems.insert(item);

        if (parentId != null) {
            parent.plannedHours = null;
            parent.touch(now);
            workItems.update(parent);
            events.publish(new HierarchyChanged(parentId, actor, source, Map.of("childAdded", false), Map.of("childAdded", id.toString())));
        }

        Map<String, Object> auditNew = new LinkedHashMap<>();
        auditNew.put("type", type.name()); auditNew.put("title", title); auditNew.put("statusId", statusId.toString());
        auditNew.put("priorityId", priorityId.toString()); auditNew.put("assigneeId", assignee);
        if (source != null) { auditNew.put("externalSource", source); auditNew.put("externalDefectId", input.get("externalDefectId")); }
        events.publish(new WorkItemCreated(id, actor, source, auditNew));

        return view.execute(id);
    }

    private static String nullableString(Object value) {
        return value == null || value.toString().isBlank() ? null : value.toString().trim();
    }
}
