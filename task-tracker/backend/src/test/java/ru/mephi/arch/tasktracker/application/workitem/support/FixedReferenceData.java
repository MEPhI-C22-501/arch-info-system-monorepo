package ru.mephi.arch.tasktracker.application.workitem.support;

import ru.mephi.arch.tasktracker.application.port.PriorityRepository;
import ru.mephi.arch.tasktracker.application.port.StatusRepository;
import ru.mephi.arch.tasktracker.application.port.TypeSettingRepository;
import ru.mephi.arch.tasktracker.application.port.UserDirectoryRepository;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.util.Set;
import java.util.UUID;

/** Small fixed-answer fakes for the reference-data ports — real correctness is Jdbc*RepositoryTest's job. */
public final class FixedReferenceData {
    private FixedReferenceData() {}

    public static final UUID DEFAULT_STATUS = UUID.randomUUID();
    public static final UUID DEFAULT_PRIORITY = UUID.randomUUID();

    public static StatusRepository statuses(UUID... inactive) {
        Set<UUID> inactiveSet = Set.of(inactive);
        return new StatusRepository() {
            @Override public boolean isActive(UUID id) { return !inactiveSet.contains(id); }
            @Override public UUID defaultStatusId() { return DEFAULT_STATUS; }
            @Override public StatusSummary findSummary(UUID id) { return new StatusSummary("Status", "OPEN"); }
        };
    }

    public static PriorityRepository priorities(UUID... inactive) {
        Set<UUID> inactiveSet = Set.of(inactive);
        return new PriorityRepository() {
            @Override public boolean isActive(UUID id) { return !inactiveSet.contains(id); }
            @Override public UUID defaultPriorityId() { return DEFAULT_PRIORITY; }
        };
    }

    public static TypeSettingRepository allTypesEnabled() {
        return type -> true;
    }

    public static TypeSettingRepository typesEnabledExcept(WorkItemType... disabled) {
        Set<WorkItemType> disabledSet = Set.of(disabled);
        return type -> !disabledSet.contains(type);
    }

    public static UserDirectoryRepository activeUsers(String... users) {
        Set<String> active = Set.of(users);
        return active::contains;
    }
}
