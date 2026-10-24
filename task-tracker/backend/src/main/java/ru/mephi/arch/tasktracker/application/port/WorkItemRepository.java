package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.workitem.HoursSummary;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface WorkItemRepository {
    /** Throws ApiException.missing("workItemId") if not found — same contract as the old raw(id). */
    WorkItem getById(UUID id);

    Optional<WorkItem> findById(UUID id);

    void insert(WorkItem item);

    void update(WorkItem item);

    void delete(UUID id);

    boolean hasChildren(UUID id);

    List<WorkItem.ChildSummary> findChildren(UUID id);

    HoursSummary computeHoursSummary(UUID id);

    /** The item's current iteration, if it's a member of one that hasn't completed yet. */
    Optional<UUID> findCurrentUnfinishedIterationId(UUID id);

    /** True if {@code candidateAncestorId} appears when walking up {@code startFromId}'s own parent chain
     * (including {@code startFromId} itself) — used to reject cycles before they're created. */
    boolean isAncestor(UUID candidateAncestorId, UUID startFromId);

    Optional<UUID> findNearestProjectAncestor(UUID id);

    /** All leaf (childless) items in {@code rootId}'s own subtree, {@code rootId} included if it's itself a leaf. */
    List<UUID> findLeafDescendantIds(UUID rootId);

    WorkItemPage search(WorkItemFilter filter);

    Optional<WorkItem> findByExternalReference(String source, String externalId);

    /** Serializes concurrent creation attempts for the same external reference within the current transaction. */
    void acquireExternalReferenceLock(String source, String externalId);

    /** Bumps version/updatedAt with no field change — used on a parent when a child is added/removed. */
    void touch(UUID id);

    /** Pessimistic row lock, held for the rest of the transaction — guards the "already in an
     * unfinished iteration" check in AddWorkItemToIteration against a concurrent add. */
    void lockForUpdate(UUID id);

    record WorkItemFilter(String type, UUID statusId, UUID priorityId, String assigneeId, UUID iterationId,
                           String search, String sort, String restrictToAssigneeId, int page, int size) {}

    record WorkItemPage(List<WorkItem> items, int page, int size, long total) {}
}
