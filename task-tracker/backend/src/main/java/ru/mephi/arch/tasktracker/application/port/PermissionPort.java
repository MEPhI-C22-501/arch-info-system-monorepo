package ru.mephi.arch.tasktracker.application.port;

/** Fronts the existing DB-seeded RBAC model (role_permission/local_access — see CLAUDE.md); the
 * model itself isn't changing, use cases just depend on this instead of the concrete AccessService. */
public interface PermissionPort {
    String currentSubject();
    String currentRole();
    void require(String permission);
    void requireItemReadable(String assigneeExternalId);
    void requireItemWritable(String assigneeExternalId);
}
