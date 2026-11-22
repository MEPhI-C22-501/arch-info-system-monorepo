package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.util.Map;
import java.util.UUID;

@Service
public class GetWorkItem {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final ViewWorkItem view;
    public GetWorkItem(WorkItemRepository workItems, PermissionPort permissions, ViewWorkItem view) {
        this.workItems = workItems; this.permissions = permissions; this.view = view;
    }

    public Map<String, Object> execute(UUID id) {
        WorkItem item = workItems.getById(id);
        permissions.requireItemReadableOrQa(item.assigneeId);
        var result = view.execute(id);
        if (item.parentId != null) {
            workItems.findById(item.parentId).ifPresent(parent -> {
                try {
                    permissions.requireItemReadableOrQa(parent.assigneeId);
                } catch (ApiException e) {
                    if (e.status == 403) return;
                    throw e;
                }
                result.put("parentLink", Map.of("id", parent.id, "title", parent.title));
            });
        }
        return result;
    }
}
