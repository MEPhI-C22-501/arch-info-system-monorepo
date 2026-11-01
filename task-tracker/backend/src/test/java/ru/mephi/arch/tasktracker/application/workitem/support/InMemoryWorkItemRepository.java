package ru.mephi.arch.tasktracker.application.workitem.support;

import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.WorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.HoursSummary;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.math.BigDecimal;
import java.util.*;

/** In-memory fake for use-case tests — no SQL, no Spring. Good enough to exercise business rules;
 * real SQL correctness (the recursive CTEs, the dynamic WHERE) is covered separately by
 * JdbcWorkItemRepositoryTest against a real Postgres via Testcontainers. */
public class InMemoryWorkItemRepository implements WorkItemRepository {
    public final Map<UUID, WorkItem> items = new LinkedHashMap<>();
    public int touchCount = 0;

    @Override public WorkItem getById(UUID id) { return findById(id).orElseThrow(() -> ApiException.missing("workItemId")); }
    @Override public Optional<WorkItem> findById(UUID id) { return Optional.ofNullable(items.get(id)); }
    @Override public void insert(WorkItem item) { items.put(item.id, item); }
    @Override public void update(WorkItem item) { items.put(item.id, item); }
    @Override public void delete(UUID id) { items.remove(id); }

    @Override public boolean hasChildren(UUID id) { return items.values().stream().anyMatch(w -> id.equals(w.parentId)); }

    @Override public List<WorkItem.ChildSummary> findChildren(UUID id) {
        return items.values().stream().filter(w -> id.equals(w.parentId))
            .map(w -> new WorkItem.ChildSummary(w.id, w.type, w.title, w.statusId)).toList();
    }

    @Override public HoursSummary computeHoursSummary(UUID id) {
        return new HoursSummary(BigDecimal.ZERO, BigDecimal.ZERO, 0L);
    }

    @Override public Optional<UUID> findCurrentUnfinishedIterationId(UUID id) { return Optional.empty(); }

    @Override public boolean isAncestor(UUID candidateAncestorId, UUID startFromId) {
        UUID cursor = startFromId;
        while (cursor != null) {
            if (cursor.equals(candidateAncestorId)) return true;
            var item = items.get(cursor);
            cursor = item == null ? null : item.parentId;
        }
        return false;
    }

    @Override public List<UUID> findLeafDescendantIds(UUID rootId) {
        List<UUID> leaves = new ArrayList<>();
        Deque<UUID> stack = new ArrayDeque<>(List.of(rootId));
        while (!stack.isEmpty()) {
            UUID current = stack.pop();
            var children = items.values().stream().filter(w -> current.equals(w.parentId)).map(w -> w.id).toList();
            if (children.isEmpty()) leaves.add(current); else stack.addAll(children);
        }
        return leaves;
    }

    @Override public Optional<UUID> findNearestProjectAncestor(UUID id) {
        UUID cursor = id;
        while (cursor != null) {
            var item = items.get(cursor);
            if (item == null) return Optional.empty();
            if (item.type == ru.mephi.arch.tasktracker.domain.workitem.WorkItemType.PROJECT) return Optional.of(item.id);
            cursor = item.parentId;
        }
        return Optional.empty();
    }

    @Override public WorkItemPage search(WorkItemFilter filter) {
        var matched = items.values().stream()
            .filter(w -> filter.type() == null || filter.type().isBlank() || filter.type().equals(w.type.name()))
            .filter(w -> filter.statusId() == null || filter.statusId().equals(w.statusId))
            .filter(w -> filter.priorityId() == null || filter.priorityId().equals(w.priorityId))
            .filter(w -> filter.assigneeId() == null || filter.assigneeId().isBlank() || filter.assigneeId().equals(w.assigneeId))
            .filter(w -> filter.restrictToAssigneeId() == null || filter.restrictToAssigneeId().equals(w.assigneeId))
            .filter(w -> filter.search() == null || filter.search().isBlank() || w.title.toLowerCase().contains(filter.search().toLowerCase()))
            .toList();
        return new WorkItemPage(matched, filter.page(), filter.size(), matched.size());
    }

    @Override public Optional<WorkItem> findByExternalReference(String source, String externalId) {
        return items.values().stream().filter(w -> Objects.equals(source, w.externalSource) && Objects.equals(externalId, w.externalDefectId)).findFirst();
    }

    @Override public void acquireExternalReferenceLock(String source, String externalId) { }

    @Override public void touch(UUID id) {
        touchCount++;
        var item = items.get(id);
        if (item != null) item.touch(java.time.OffsetDateTime.now());
    }

    @Override public void lockForUpdate(UUID id) { }
}
