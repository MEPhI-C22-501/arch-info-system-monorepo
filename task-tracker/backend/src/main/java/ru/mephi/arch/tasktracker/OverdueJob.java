package ru.mephi.arch.tasktracker;

import org.springframework.stereotype.Component;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.jdbc.core.JdbcTemplate;
import java.util.UUID;

@Component
public class OverdueJob {
    private final JdbcTemplate db;
    private final ChangeRecorder changes;
    public OverdueJob(JdbcTemplate db,ChangeRecorder changes) { this.db=db; this.changes=changes; }
    @Scheduled(cron="0 0 * * * *",zone="Europe/Moscow") @Transactional
    public void run() {
        for(var row:db.queryForList("SELECT w.* FROM work_item w JOIN status s ON s.id=w.status_id WHERE s.category='OPEN' AND w.assignee_external_id IS NOT NULL AND w.due_date<(now() AT TIME ZONE 'Europe/Moscow')::date")) {
            int added=db.update("INSERT INTO overdue_delivery VALUES(?,?,?) ON CONFLICT DO NOTHING",row.get("id"),row.get("due_date"),row.get("assignee_external_id"));
            if(added>0) changes.notify((String)row.get("assignee_external_id"),(UUID)row.get("id"),row.get("id").toString(),(String)row.get("title"),"Просрочен срок задачи", "system");
        }
    }
}
