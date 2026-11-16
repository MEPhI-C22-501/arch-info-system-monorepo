package ru.mephi.arch.tasktracker.application.port;

public interface PermissionPort {
    String currentSubject();
    boolean ownOnly(String permission);
    void require(String permission);
    void requireItemReadable(String assigneeExternalId);
    void requireItemReadableOrQa(String assigneeExternalId);
    void requireItemWritable(String assigneeExternalId);
}
