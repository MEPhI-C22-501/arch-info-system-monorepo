package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.StatusRepository;
import ru.mephi.arch.tasktracker.application.port.TimeLogRepository;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.application.workitem.ViewWorkItem;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;

/**
 * Application-layer composition, not a domain method — it spans the work-item tree, time logs,
 * capacity entries, and status lookups, crossing aggregate boundaries (see the restructuring
 * plan's rationale). Mirrors the old private {@code IterationService.metrics()} field-for-field.
 */
@Service
public class IterationMetricsCalculator {
    private final IterationRepository iterations;
    private final WorkItemRepository workItems;
    private final TimeLogRepository timeLogs;
    private final StatusRepository statuses;
    private final ViewWorkItem viewWorkItem;

    public IterationMetricsCalculator(IterationRepository iterations, WorkItemRepository workItems,
                                       TimeLogRepository timeLogs, StatusRepository statuses, ViewWorkItem viewWorkItem) {
        this.iterations = iterations; this.workItems = workItems; this.timeLogs = timeLogs;
        this.statuses = statuses; this.viewWorkItem = viewWorkItem;
    }

    public Map<String, Object> compute(UUID iterationId) {
        Iteration iteration = iterations.getById(iterationId);
        List<UUID> selected = iterations.findActiveMemberIds(iterationId);
        Set<UUID> leafIds = new LinkedHashSet<>();
        List<Map<String, Object>> itemViews = new ArrayList<>();
        Map<String, Integer> statusCounts = new TreeMap<>();
        int completeCount = 0;
        List<String> warnings = new ArrayList<>();

        for (UUID itemId : selected) {
            Map<String, Object> view = viewWorkItem.execute(itemId);
            itemViews.add(view);
            var status = statuses.findSummary((UUID) view.get("statusId"));
            statusCounts.merge(status.name(), 1, Integer::sum);
            if ("COMPLETED".equals(status.category())) completeCount++;
            Object dueDate = view.get("dueDate");
            if (dueDate instanceof LocalDate due && (due.isBefore(iteration.startDate) || due.isAfter(iteration.endDate))) {
                warnings.add("Срок вне итерации: " + itemId);
            }
            leafIds.addAll(workItems.findLeafDescendantIds(itemId));
        }

        BigDecimal planned = BigDecimal.ZERO;
        BigDecimal actual = BigDecimal.ZERO;
        Map<String, BigDecimal> load = new TreeMap<>();
        Map<String, BigDecimal> spentByAssignee = new TreeMap<>();
        for (UUID leaf : leafIds) {
            var item = workItems.getById(leaf);
            BigDecimal hours = item.plannedHours;
            if (hours == null) warnings.add("Нет оценки: " + leaf); else planned = planned.add(hours);
            String assignee = item.assigneeId;
            if (assignee == null) warnings.add("Нет исполнителя: " + leaf);
            else load.merge(assignee, hours == null ? BigDecimal.ZERO : hours, BigDecimal::add);
            BigDecimal spent = timeLogs.sumHoursForWorkItem(leaf);
            actual = actual.add(spent);
            if (assignee != null) spentByAssignee.merge(assignee, spent, BigDecimal::add);
        }

        List<Map<String, Object>> capacityOut = new ArrayList<>();
        BigDecimal totalCapacity = BigDecimal.ZERO;
        var capacities = iterations.findCapacity(iterationId);
        Set<String> users = new TreeSet<>(load.keySet());
        capacities.forEach(c -> users.add(c.externalUserId()));
        for (String user : users) {
            BigDecimal available = capacities.stream().filter(c -> c.externalUserId().equals(user))
                .map(ru.mephi.arch.tasktracker.domain.iteration.CapacityEntry::availableHours).findFirst().orElse(BigDecimal.ZERO);
            totalCapacity = totalCapacity.add(available);
            BigDecimal assigned = load.getOrDefault(user, BigDecimal.ZERO);
            capacityOut.add(Map.of("userId", user, "availableHours", available, "plannedHours", assigned,
                "actualHours", spentByAssignee.getOrDefault(user, BigDecimal.ZERO),
                "reserveHours", available.subtract(assigned), "overloaded", assigned.compareTo(available) > 0));
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("items", itemViews); result.put("statusCounts", statusCounts);
        result.put("plannedHours", planned); result.put("actualHours", actual); result.put("remainingHours", planned.subtract(actual));
        result.put("capacity", capacityOut); result.put("teamCapacityHours", totalCapacity); result.put("teamReserveHours", totalCapacity.subtract(planned));
        result.put("completedCount", completeCount);
        result.put("completionFraction", selected.isEmpty() ? 0.0 : (double) completeCount / selected.size());
        result.put("warnings", warnings);
        return result;
    }
}
