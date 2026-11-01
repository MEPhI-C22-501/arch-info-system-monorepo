package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;

import java.util.Map;

@Service
public class ListWorkItems {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final ViewWorkItem view;
    public ListWorkItems(WorkItemRepository workItems, PermissionPort permissions, ViewWorkItem view) {
        this.workItems = workItems; this.permissions = permissions; this.view = view;
    }

    public Map<String, Object> execute(Map<String, String> filters) {
        permissions.require("item.read");
        int page = Math.max(1, parseInt(filters.get("page"), 1));
        int size = Math.min(500, Math.max(1, parseInt(filters.get("pageSize"), 50)));
        String restrictToAssigneeId = "MEMBER".equals(permissions.currentRole()) ? permissions.currentSubject() : null;
        var filter = new WorkItemRepository.WorkItemFilter(
            filters.get("type"), Values.uuid(filters.get("statusId"), "statusId"), Values.uuid(filters.get("priorityId"), "priorityId"),
            filters.get("assigneeId"), Values.uuid(filters.get("iterationId"), "iterationId"),
            filters.get("search"), filters.get("sort"), restrictToAssigneeId, page, size);
        var result = workItems.search(filter);
        long totalPages = (result.total() + size - 1) / size;
        return Map.of("items", result.items().stream().map(w -> view.execute(w.id)).toList(),
            "page", page, "pageSize", size, "totalPages", totalPages, "total", result.total());
    }

    private int parseInt(String value, int fallback) {
        try { return value == null ? fallback : Integer.parseInt(value); }
        catch (NumberFormatException e) { throw ApiException.invalid("page", "invalid_integer"); }
    }
}
