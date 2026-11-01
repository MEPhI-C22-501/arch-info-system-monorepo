package ru.mephi.arch.tasktracker.domain.iteration;

import org.junit.jupiter.api.Test;
import ru.mephi.arch.tasktracker.ApiException;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class IterationTest {
    private Iteration iteration(IterationState state) {
        return new Iteration(UUID.randomUUID(), "Sprint", "", LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 14), state, OffsetDateTime.now());
    }

    @Test void completedIterationIsNotEditable() {
        var e = assertThrows(ApiException.class, () -> iteration(IterationState.COMPLETED).ensureEditable());
        assertEquals("completed", e.getMessage());
    }

    @Test void plannedAndActiveIterationsAreEditable() {
        assertDoesNotThrow(() -> iteration(IterationState.PLANNED).ensureEditable());
        assertDoesNotThrow(() -> iteration(IterationState.ACTIVE).ensureEditable());
    }
}
