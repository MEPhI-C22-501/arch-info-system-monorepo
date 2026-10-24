package ru.mephi.arch.tasktracker.application.workitem;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.HoursSummary;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Pure assembly, no permission check — mirrors the old private {@code view()} helper used
 * internally by create/update/list as well as by the permission-checked read path. */
@Service
public class ViewWorkItem {
    private final WorkItemRepository workItems;
    public ViewWorkItem(WorkItemRepository workItems) { this.workItems = workItems; }

    public Map<String, Object> execute(UUID id) {
        WorkItem item = workItems.getById(id);
        HoursSummary hours = workItems.computeHoursSummary(id);
        UUID iterationId = workItems.findCurrentUnfinishedIterationId(id).orElse(null);
        var children = workItems.findChildren(id);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", item.id); out.put("type", item.type.name()); out.put("title", item.title);
        out.put("description", item.description); out.put("statusId", item.statusId); out.put("priorityId", item.priorityId);
        out.put("assigneeId", item.assigneeId); out.put("startDate", item.startDate); out.put("dueDate", item.dueDate);
        out.put("plannedHours", hours.planned()); out.put("actualHours", hours.actual()); out.put("remainingHours", hours.remaining());
        out.put("unestimatedLeaves", hours.unestimatedLeafCount());
        out.put("parentId", item.parentId); out.put("version", item.version);
        out.put("createdAt", item.createdAt); out.put("updatedAt", item.updatedAt);
        out.put("externalSource", item.externalSource); out.put("externalDefectId", item.externalDefectId);
        out.put("severity", item.severity); out.put("environment", item.environment);
        out.put("testRunUrl", item.testRunUrl); out.put("testCaseUrl", item.testCaseUrl);
        out.put("iterationId", iterationId);
        out.put("children", children.stream()
            .map(c -> Map.of("id", c.id(), "type", c.type().name(), "title", c.title(), "statusId", c.statusId()))
            .toList());
        return out;
    }
}
