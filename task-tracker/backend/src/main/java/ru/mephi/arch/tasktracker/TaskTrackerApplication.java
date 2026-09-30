package ru.mephi.arch.tasktracker;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class TaskTrackerApplication {
    public static void main(String[] args) { SpringApplication.run(TaskTrackerApplication.class, args); }
}
