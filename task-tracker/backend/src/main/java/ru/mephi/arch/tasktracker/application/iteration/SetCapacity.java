package ru.mephi.arch.tasktracker.application.iteration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.mephi.arch.tasktracker.ApiException;
import ru.mephi.arch.tasktracker.Values;
import ru.mephi.arch.tasktracker.application.port.IterationRepository;
import ru.mephi.arch.tasktracker.application.port.PermissionPort;
import ru.mephi.arch.tasktracker.application.port.UserDirectoryRepository;

import java.util.Map;
import java.util.UUID;

@Service
public class SetCapacity {
    private final IterationRepository iterations;
    private final PermissionPort permissions;
    private final UserDirectoryRepository directory;
    private final ViewIteration view;
    public SetCapacity(IterationRepository iterations, PermissionPort permissions, UserDirectoryRepository directory, ViewIteration view) {
        this.iterations = iterations; this.permissions = permissions; this.directory = directory; this.view = view;
    }

    @Transactional
    public Map<String, Object> execute(UUID id, Map<String, Object> body) {
        permissions.require("capacity.write");
        var iteration = iterations.getById(id);
        iteration.ensureEditable();
        String user = Values.str(body, "userId", true);
        var hours = Values.hours(body.get("availableHours"), "availableHours", false);
        if (hours == null) throw ApiException.invalid("availableHours", "required");
        if (!directory.isActive(user)) throw ApiException.invalid("userId", "unknown_or_inactive");
        iterations.upsertCapacity(id, user, hours);
        return view.execute(id);
    }
}
