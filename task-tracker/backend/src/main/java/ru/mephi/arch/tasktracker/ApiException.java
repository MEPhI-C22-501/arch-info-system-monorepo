package ru.mephi.arch.tasktracker;

public class ApiException extends RuntimeException {
    public final int status;
    public final String field;
    public ApiException(int status, String field, String reason) {
        super(reason);
        this.status = status;
        this.field = field;
    }
    public static ApiException invalid(String field, String reason) { return new ApiException(422, field, reason); }
    public static ApiException conflict(String field, String reason) { return new ApiException(409, field, reason); }
    public static ApiException missing(String field) { return new ApiException(404, field, "not_found"); }
}
