package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.*;
import ru.mephi.arch.tasktracker.domain.event.HierarchyChanged;
import ru.mephi.arch.tasktracker.domain.event.WorkItemFieldsChanged;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemFactory;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/**
 * {@code item.status} is checked here, inside, whenever the status is actually changing — unlike
 * {@code item.update}'s ownership check, which stays in the controller, this one must fire for
 * every caller including Excel import, so it can't move out (see CLAUDE.md / the restructuring plan).
 */
@Service
public class UpdateWorkItem {
    private final WorkItemRepository workItems;
    private final StatusRepository statuses;
    private final PriorityRepository priorities;
    private final UserDirectoryRepository directory;
    private final PermissionPort permissions;
    private final EventPublisherPort events;
    private final ViewWorkItem view;

    public UpdateWorkItem(WorkItemRepository workItems, StatusRepository statuses, PriorityRepository priorities,
                           UserDirectoryRepository directory, PermissionPort permissions, EventPublisherPort events,
                           ViewWorkItem view) {
        this.workItems = workItems; this.statuses = statuses; this.priorities = priorities;
        this.directory = directory; this.permissions = permissions; this.events = events; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID id, Map<String, Object> input, String actor, String source) {
        WorkItem before = workItems.getById(id);
        if (input.containsKey("version") && Long.parseLong(input.get("version").toString()) != before.version) {
            throw ApiException.conflict("version", "stale_work_item");
        }
        String title = nullableString(field(input, "title", before.title));
        if (title == null) throw ApiException.invalid("title", "required");
        if (input.containsKey("type") && !before.type.name().equals(input.get("type"))) {
            throw ApiException.invalid("type", "immutable");
        }

        UUID statusId = before.statusId;
        if (input.containsKey("statusId")) {
            UUID requested = Values.uuid(input.get("statusId"), "statusId");
            if (!statusId.equals(requested)) permissions.require("item.status");
            if (!statuses.isActive(requested)) throw ApiException.invalid("statusId", "unknown_or_inactive");
            statusId = requested;
        }
        UUID priorityId = before.priorityId;
        if (input.containsKey("priorityId")) {
            priorityId = Values.uuid(input.get("priorityId"), "priorityId");
            if (!priorities.isActive(priorityId)) throw ApiException.invalid("priorityId", "unknown_or_inactive");
        }

        UUID parentId = input.containsKey("parentId") ? Values.uuid(input.get("parentId"), "parentId") : before.parentId;
        WorkItem parent = parentId == null ? null : workItems.getById(parentId);
        WorkItemFactory.validateParentage(id, before.type, parentId, parent);
        if (parentId != null && workItems.isAncestor(id, parentId)) throw ApiException.invalid("parentId", "cycle");

        String assignee = nullableString(field(input, "assigneeId", before.assigneeId));
        if (!Objects.equals(before.assigneeId, assignee) && assignee != null && !directory.isActive(assignee)) {
            throw ApiException.invalid("assigneeId", "unknown_or_inactive");
        }
        LocalDate start = Values.date(field(input, "startDate", before.startDate), "startDate");
        LocalDate due = Values.date(field(input, "dueDate", before.dueDate), "dueDate");
        WorkItemFactory.validateDates(start, due);
        BigDecimal planned = Values.hours(field(input, "plannedHours", before.plannedHours), "plannedHours", false);
        WorkItemFactory.validatePlannedHoursAllowed(before.type, planned);
        if (planned != null && workItems.hasChildren(id)) throw ApiException.invalid("plannedHours", "parent_is_computed");
        String description = Objects.toString(field(input, "description", before.description), "");

        Map<String, Object> oldVals = snapshot(before);
        Map<String, Object> newVals = new LinkedHashMap<>();
        newVals.put("title", title); newVals.put("description", description); newVals.put("statusId", statusId.toString());
        newVals.put("priorityId", priorityId.toString()); newVals.put("assigneeId", assignee);
        newVals.put("startDate", start == null ? null : start.toString()); newVals.put("dueDate", due == null ? null : due.toString());
        newVals.put("plannedHours", planned); newVals.put("parentId", parentId == null ? null : parentId.toString());
        if (oldVals.equals(newVals)) return view.execute(id);

        UUID oldParentId = before.parentId;
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        before.applyFieldUpdate(title, description, statusId, priorityId, assignee, start, due, planned, parentId, now);
        workItems.update(before);

        if (!Objects.equals(oldParentId, parentId)) {
            if (oldParentId != null) {
                workItems.touch(oldParentId);
                events.publish(new HierarchyChanged(oldParentId, actor, source, Map.of("childRemoved", false), Map.of("childRemoved", id.toString())));
            }
            if (parentId != null) {
                parent.plannedHours = null;
                parent.touch(now);
                workItems.update(parent);
                events.publish(new HierarchyChanged(parentId, actor, source, Map.of("childAdded", false), Map.of("childAdded", id.toString())));
            }
        }
        events.publish(new WorkItemFieldsChanged(id, actor, source, oldVals, newVals));
        return view.execute(id);
    }

    private Map<String, Object> snapshot(WorkItem item) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("title", item.title); result.put("description", item.description);
        result.put("statusId", item.statusId.toString()); result.put("priorityId", item.priorityId.toString());
        result.put("assigneeId", item.assigneeId);
        result.put("startDate", item.startDate == null ? null : item.startDate.toString());
        result.put("dueDate", item.dueDate == null ? null : item.dueDate.toString());
        result.put("plannedHours", item.plannedHours);
        result.put("parentId", item.parentId == null ? null : item.parentId.toString());
        return result;
    }

    private static Object field(Map<String, Object> input, String key, Object fallback) {
        return input.containsKey(key) ? input.get(key) : fallback;
    }

    private static String nullableString(Object value) {
        return value == null || value.toString().isBlank() ? null : value.toString().trim();
    }
}
