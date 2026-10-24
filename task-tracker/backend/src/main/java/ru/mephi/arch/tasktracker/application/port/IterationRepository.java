package ru.mephi.arch.tasktracker.application.port;

import ru.mephi.arch.tasktracker.domain.iteration.CapacityEntry;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/** Capacity entries and work-item membership are child data of the Iteration aggregate here —
 * not independent aggregates, same as CollaborationService's comments/time-logs/attachments are
 * their own repositories only because they're independently addressable sub-resources. */
public interface IterationRepository {
    Iteration getById(UUID id);

    List<Iteration> findAll();

    void insert(Iteration iteration);

    void update(Iteration iteration);

    void activate(UUID id, Map<String, Object> baselineSnapshot);

    void complete(UUID id, Map<String, Object> resultSnapshot);

    Optional<Map<String, Object>> findBaselineSnapshot(UUID id);

    Optional<Map<String, Object>> findResultSnapshot(UUID id);

    /** Active (not-removed) member work-item ids, in the order they were added. */
    List<UUID> findActiveMemberIds(UUID iterationId);

    boolean isMember(UUID iterationId, UUID workItemId);

    boolean hasOtherUnfinishedMembership(UUID workItemId, UUID excludingIterationId);

    void addMember(UUID iterationId, UUID workItemId);

    /** Returns false if there was no active membership to remove. */
    boolean removeMember(UUID iterationId, UUID workItemId);

    void upsertCapacity(UUID iterationId, String externalUserId, BigDecimal availableHours);

    List<CapacityEntry> findCapacity(UUID iterationId);
}
