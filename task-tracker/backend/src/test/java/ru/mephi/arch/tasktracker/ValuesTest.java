package ru.mephi.arch.tasktracker;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

class ValuesTest {
    @Test void requiredTextIsTrimmedAndBlankRejected() {
        assertEquals("Задача", Values.str(Map.of("title", "  Задача  "), "title", true));
        assertEquals("required", assertThrows(ApiException.class,
            () -> Values.str(Map.of("title", "  "), "title", true)).getMessage());
    }

    @Test void hoursHaveTwoDecimalPlacesAndNonNegativeEstimate() {
        assertEquals(new BigDecimal("0.25"), Values.hours("0.25", "hours", true));
        assertEquals(BigDecimal.ZERO, Values.hours("0", "hours", false));
        for (String bad : new String[] {"-1", "1.234", "not-a-number"})
            assertEquals("invalid_hours", assertThrows(ApiException.class,
                () -> Values.hours(bad, "hours", false)).getMessage());
        assertThrows(ApiException.class, () -> Values.hours("0", "hours", true));
    }

    @Test void datesAndIdentifiersAreStrict() {
        UUID id = UUID.randomUUID();
        assertEquals(id, Values.uuid(id.toString(), "id"));
        assertEquals(LocalDate.of(2026, 9, 28), Values.date("2026-09-28", "date"));
        assertEquals("invalid_uuid", assertThrows(ApiException.class,
            () -> Values.uuid("bad", "id")).getMessage());
        assertEquals("invalid_date", assertThrows(ApiException.class,
            () -> Values.date("28.09.2026", "date")).getMessage());
    }

    @Test void onlySupportedItemTypesAccepted() {
        for (String type : new String[] {"PROJECT", "EPIC", "TASK", "BUG", "SUBTASK"})
            assertEquals(type, Values.type(type));
        assertThrows(ApiException.class, () -> Values.type("STORY"));
    }
}
