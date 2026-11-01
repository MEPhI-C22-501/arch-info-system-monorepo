package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.EventPublisherPort;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.event.HierarchyChanged;
import ru.mephi.arch.tasktracker.domain.event.WorkItemHardDeleted;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.util.Map;
import java.util.UUID;

@Service
public class DeleteWorkItem {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final EventPublisherPort events;
    public DeleteWorkItem(WorkItemRepository workItems, PermissionPort permissions, EventPublisherPort events) {
        this.workItems = workItems; this.permissions = permissions; this.events = events;
    }

    @Transactional
    public void execute(UUID id, String confirmation) {
        permissions.require("item.delete");
        if (!id.toString().equals(confirmation)) throw ApiException.invalid("confirmationId", "confirmation_required");
        WorkItem item = workItems.getById(id);
        if (workItems.hasChildren(id)) throw ApiException.conflict("children", "move_or_delete_children_first");
        workItems.delete(id);
        String actor = permissions.currentSubject();
        if (item.parentId != null) {
            workItems.touch(item.parentId);
            events.publish(new HierarchyChanged(item.parentId, actor, null,
                Map.of("childRemoved", false), Map.of("childRemoved", id.toString())));
        }
        events.publish(new WorkItemHardDeleted(item.assigneeId, id.toString(), item.title, actor));
    }
}
