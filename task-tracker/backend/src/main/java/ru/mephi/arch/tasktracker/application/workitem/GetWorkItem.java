package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
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
        return view.execute(id);
    }
}
