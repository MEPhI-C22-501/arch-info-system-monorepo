package ru.mephi.arch.tasktracker.application.workitem;

import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.workitem.support.FakePermissionPort;
import ru.mephi.arch.tasktracker.application.workitem.support.InMemoryWorkItemRepository;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItem;
import ru.mephi.arch.tasktracker.domain.workitem.WorkItemType;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class GetWorkItemTest {
    private final InMemoryWorkItemRepository items = new InMemoryWorkItemRepository();
    private final FakePermissionPort permissions = new FakePermissionPort();
    private final GetWorkItem get = new GetWorkItem(items, permissions, new ViewWorkItem(items));

    @Test void hierarchyLinkIsAvailableOnlyForAReadableParent() {
        UUID parent = add(WorkItemType.TASK, "Parent", "another-member", null);
        UUID child = add(WorkItemType.SUBTASK, "Child", permissions.subject, parent);

        var restricted = get.execute(child);
        assertEquals(parent, restricted.get("parentId"));
        assertFalse(restricted.containsKey("parentLink"));
        assertEquals(403, assertThrows(ApiException.class, () -> get.execute(parent)).status);

        permissions.role = "LEAD";
        assertEquals(Map.of("id", parent, "title", "Parent"), get.execute(child).get("parentLink"));
        assertFalse(get.execute(parent).containsKey("parentLink"));
    }

    private UUID add(WorkItemType type, String title, String assignee, UUID parent) {
        UUID id = UUID.randomUUID();
        var now = OffsetDateTime.now();
        items.insert(new WorkItem(id, type, title, "", UUID.randomUUID(), UUID.randomUUID(), assignee,
            null, null, null, parent, null, null, null, null, null, null, 0, now, now));
        return id;
    }
}
