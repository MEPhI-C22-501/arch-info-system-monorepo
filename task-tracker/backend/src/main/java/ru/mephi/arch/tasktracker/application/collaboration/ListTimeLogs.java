package ru.mephi.arch.tasktracker.application.collaboration;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.TimeLogRepository;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ListTimeLogs {
    private final WorkItemRepository workItems;
    private final PermissionPort permissions;
    private final TimeLogRepository timeLogs;
    public ListTimeLogs(WorkItemRepository workItems, PermissionPort permissions, TimeLogRepository timeLogs) {
        this.workItems = workItems; this.permissions = permissions; this.timeLogs = timeLogs;
    }

    public List<Map<String, Object>> execute(UUID workItemId) {
        permissions.requireItemReadable(workItems.getById(workItemId).assigneeId);
        return timeLogs.findByWorkItem(workItemId).stream()
            .<Map<String, Object>>map(entry -> Map.of("id", entry.id, "userId", entry.externalUserId,
                "loggedDate", entry.loggedDate, "hours", entry.hours, "comment", entry.comment, "createdAt", entry.createdAt))
            .toList();
    }
}
