package ru.mephi.arch.tasktracker;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;

public final class Values {
    private Values() {}
    public static String str(Map<String,?> data, String field, boolean required) {
        Object value = data.get(field);
        if (value == null) { if (required) throw ApiException.invalid(field,"required"); return null; }
        String result = value.toString().trim();
        if (required && result.isEmpty()) throw ApiException.invalid(field,"required");
        return result;
    }
    public static UUID uuid(Object value, String field) {
        if (value == null || value.toString().isBlank()) return null;
        try { return UUID.fromString(value.toString()); } catch (IllegalArgumentException e) { throw ApiException.invalid(field,"invalid_uuid"); }
    }
    public static UUID requiredUuid(Map<String,?> data, String field) {
        UUID result = uuid(data.get(field), field);
        if (result == null) throw ApiException.invalid(field,"required");
        return result;
    }
    public static BigDecimal hours(Object value, String field, boolean positive) {
        if (value == null || value.toString().isBlank()) return null;
        try {
            BigDecimal result = new BigDecimal(value.toString());
            if (result.scale() > 2 || (positive ? result.signum() <= 0 : result.signum() < 0)) throw new NumberFormatException();
            return result;
        } catch (NumberFormatException e) { throw ApiException.invalid(field,"invalid_hours"); }
    }
    public static LocalDate date(Object value, String field) {
        if (value == null || value.toString().isBlank()) return null;
        try { return LocalDate.parse(value.toString()); } catch (Exception e) { throw ApiException.invalid(field,"invalid_date"); }
    }
    public static String type(String value) {
        if (value == null || !java.util.Set.of("PROJECT","EPIC","TASK","BUG","SUBTASK").contains(value)) throw ApiException.invalid("type","invalid_type");
        return value;
    }
}
