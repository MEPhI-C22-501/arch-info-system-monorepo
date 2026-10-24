package ru.mephi.arch.tasktracker.infrastructure.security;

import org.springframework.stereotype.Component;
import ru.mephi.arch.tasktracker.AccessService;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;

import java.util.Collections;

/** Strangler-fig adapter: wraps the untouched {@link AccessService} rather than reimplementing
 * RBAC — that model is deliberately staying as-is (see CLAUDE.md). */
@Component
public class PermissionPortAdapter implements PermissionPort {
    private final AccessService access;
    public PermissionPortAdapter(AccessService access) { this.access = access; }

    @Override public String currentSubject() { return access.subject(); }
    @Override public String currentRole() { return access.role(); }
    @Override public void require(String permission) { access.require(permission); }

    @Override public void requireItemReadable(String assigneeExternalId) {
        access.itemRead(Collections.singletonMap("assignee_external_id", assigneeExternalId));
    }

    @Override public void requireItemWritable(String assigneeExternalId) {
        access.itemWrite(Collections.singletonMap("assignee_external_id", assigneeExternalId));
    }
}
