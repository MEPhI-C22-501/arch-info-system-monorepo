package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.AuditRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.util.List;
import java.util.Map;
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
        return audit.findByWorkItem(id);
    }
}
