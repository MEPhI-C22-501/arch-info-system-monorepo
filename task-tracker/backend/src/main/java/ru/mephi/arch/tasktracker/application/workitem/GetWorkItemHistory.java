package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.AuditRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.util.List;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class GetWorkItemHistory {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final AuditRepository audit;
    public GetWorkItemHistory(WorkItemRepository workItems, PermissionPort permissions, AuditRepository audit) {
        this.workItems = workItems; this.permissions = permissions; this.audit = audit;
    }

    public List<Map<String, Object>> execute(UUID id) {
        WorkItem item = workItems.getById(id);
        permissions.requireItemReadable(item.assigneeId);
        var entries = audit.findByWorkItem(id);
        Map<UUID, Optional<String>> names = new HashMap<>();
        for (var entry : entries) {
            Map<String, String> relatedItems = new HashMap<>();
            for (String side : List.of("oldValues", "newValues")) {
                if (!(entry.get(side) instanceof Map<?, ?> fields)) continue;
                for (String key : List.of("parentId", "childAdded", "childRemoved")) {
                    if (!(fields.get(key) instanceof String value) || value.isBlank()) continue;
                    UUID reference;
                    try { reference = UUID.fromString(value); }
                    catch (IllegalArgumentException ignored) { continue; }
                    names.computeIfAbsent(reference, this::readableTitle)
                        .ifPresent(title -> relatedItems.put(value, title));
                }
            }
            if (!relatedItems.isEmpty()) entry.put("relatedItems", relatedItems);
        }
        return entries;
    }

    private Optional<String> readableTitle(UUID id) {
        var referenced = workItems.findById(id);
        if (referenced.isEmpty()) return Optional.empty();
        try { permissions.requireItemReadable(referenced.get().assigneeId); }
        catch (ApiException e) {
            if (e.status == 403) return Optional.empty();
            throw e;
        }
        return Optional.of(referenced.get().title);
    }
}
