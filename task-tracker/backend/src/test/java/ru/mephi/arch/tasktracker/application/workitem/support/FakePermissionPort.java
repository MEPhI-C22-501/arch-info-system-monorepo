package ru.mephi.arch.tasktracker.application.workitem.support;

import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;

import java.util.Objects;
import java.util.Set;

public class FakePermissionPort implements PermissionPort {
    public String subject = "member-1";
    public String role = "MEMBER";
    public Set<String> granted = Set.of("item.create", "item.update", "item.status", "item.delete", "item.read");

    @Override public String currentSubject() { return subject; }
    @Override public String currentRole() { return role; }

    @Override public void require(String permission) {
        if (!granted.contains(permission)) throw new ApiException(403, "permission", "forbidden");
    }

    @Override public void requireItemReadable(String assigneeExternalId) {
        require("item.read");
        if ("MEMBER".equals(role) && !Objects.equals(subject, assigneeExternalId)) throw new ApiException(403, "item", "forbidden");
    }

    @Override public void requireItemReadableOrQa(String assigneeExternalId) {
        requireItemReadable(assigneeExternalId);
    }

    @Override public void requireItemWritable(String assigneeExternalId) {
        require("item.update");
        if ("MEMBER".equals(role) && !Objects.equals(subject, assigneeExternalId)) throw new ApiException(403, "item", "forbidden");
    }
}
