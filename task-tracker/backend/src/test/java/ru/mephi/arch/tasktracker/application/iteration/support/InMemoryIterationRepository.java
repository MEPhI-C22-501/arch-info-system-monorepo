package ru.mephi.arch.tasktracker.application.iteration.support;

import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.domain.iteration.CapacityEntry;
import ru.mephi.arch.tasktracker.domain.iteration.Iteration;
import ru.mephi.arch.tasktracker.domain.iteration.IterationState;

import java.math.BigDecimal;
import java.util.*;

public class InMemoryIterationRepository implements IterationRepository {
    public final Map<UUID, Iteration> iterations = new LinkedHashMap<>();
    public final Map<UUID, Map<String, Object>> baselineSnapshots = new HashMap<>();
    public final Map<UUID, Map<String, Object>> resultSnapshots = new HashMap<>();
    /** iterationId -> workItemId -> removed (true = no longer active member) */
    public final Map<UUID, Map<UUID, Boolean>> membership = new LinkedHashMap<>();
    public final Map<UUID, List<CapacityEntry>> capacity = new HashMap<>();

    @Override public Iteration getById(UUID id) {
        var iteration = iterations.get(id);
        if (iteration == null) throw ApiException.missing("iterationId");
        return iteration;
    }

    @Override public List<Iteration> findAll() { return List.copyOf(iterations.values()); }
    @Override public void insert(Iteration iteration) { iterations.put(iteration.id, iteration); }
    @Override public void update(Iteration iteration) { iterations.put(iteration.id, iteration); }

    @Override public void activate(UUID id, Map<String, Object> baselineSnapshot) {
        getById(id).state = IterationState.ACTIVE;
        baselineSnapshots.put(id, baselineSnapshot);
    }

    @Override public void complete(UUID id, Map<String, Object> resultSnapshot) {
        getById(id).state = IterationState.COMPLETED;
        resultSnapshots.put(id, resultSnapshot);
    }

    @Override public Optional<Map<String, Object>> findBaselineSnapshot(UUID id) { return Optional.ofNullable(baselineSnapshots.get(id)); }
    @Override public Optional<Map<String, Object>> findResultSnapshot(UUID id) { return Optional.ofNullable(resultSnapshots.get(id)); }

    @Override public List<UUID> findActiveMemberIds(UUID iterationId) {
        return membership.getOrDefault(iterationId, Map.of()).entrySet().stream()
            .filter(e -> !e.getValue()).map(Map.Entry::getKey).toList();
    }

    @Override public boolean isMember(UUID iterationId, UUID workItemId) {
        return !membership.getOrDefault(iterationId, Map.of()).getOrDefault(workItemId, true);
    }

    @Override public boolean hasOtherUnfinishedMembership(UUID workItemId, UUID excludingIterationId) {
        return membership.entrySet().stream().anyMatch(e -> !e.getKey().equals(excludingIterationId)
            && Boolean.FALSE.equals(e.getValue().get(workItemId))
            && iterations.get(e.getKey()).state != IterationState.COMPLETED);
    }

    @Override public void addMember(UUID iterationId, UUID workItemId) {
        membership.computeIfAbsent(iterationId, k -> new LinkedHashMap<>()).put(workItemId, false);
    }

    @Override public boolean removeMember(UUID iterationId, UUID workItemId) {
        var forIteration = membership.get(iterationId);
        if (forIteration == null || !Boolean.FALSE.equals(forIteration.get(workItemId))) return false;
        forIteration.put(workItemId, true);
        return true;
    }

    @Override public void upsertCapacity(UUID iterationId, String externalUserId, BigDecimal availableHours) {
        var list = capacity.computeIfAbsent(iterationId, k -> new ArrayList<>());
        list.removeIf(c -> c.externalUserId().equals(externalUserId));
        list.add(new CapacityEntry(externalUserId, availableHours));
    }

    @Override public List<CapacityEntry> findCapacity(UUID iterationId) { return capacity.getOrDefault(iterationId, List.of()); }
}
