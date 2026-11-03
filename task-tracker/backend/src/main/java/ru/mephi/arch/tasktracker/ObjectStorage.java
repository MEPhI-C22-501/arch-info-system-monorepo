package ru.mephi.arch.tasktracker;

import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import software.amazon.awssdk.auth.credentials.*;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.core.sync.RequestBody;
import java.net.URI;
import java.util.*;

@Component
public class ObjectStorage {
    private final S3Client client;
    private final String bucket;
    private final JdbcTemplate db;
    private final TransactionTemplate independent;
    public ObjectStorage(JdbcTemplate db, PlatformTransactionManager manager,
        @Value("${S3_ENDPOINT:}") String endpoint, @Value("${S3_BUCKET:arch-dev-task-tracker}") String bucket,
        @Value("${S3_ACCESS_KEY:}") String key,@Value("${S3_SECRET_KEY:}") String secret) {
        this.db=db; this.bucket=bucket; independent=new TransactionTemplate(manager);
        independent.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        client=endpoint.isBlank()?null:S3Client.builder().endpointOverride(URI.create(endpoint)).region(Region.US_EAST_1)
            .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create(key,secret))).forcePathStyle(true)
            .overrideConfiguration(c->c.apiCallTimeout(java.time.Duration.ofSeconds(20))).build();
    }
    public boolean enabled() { return client!=null; }
    public static String hash(byte[] bytes) {
        try { return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch(java.security.NoSuchAlgorithmException ex) { throw new IllegalStateException(ex); }
    }
    public void put(String key,byte[] bytes,String contentType) {
        independent.executeWithoutResult(s->db.update("INSERT INTO object_cleanup(object_key) VALUES(?) ON CONFLICT DO NOTHING",key));
        client.putObject(PutObjectRequest.builder().bucket(bucket).key(key).contentType(contentType).build(),RequestBody.fromBytes(bytes));
    }
    public byte[] get(String key,String expected) {
        byte[] bytes=client.getObjectAsBytes(GetObjectRequest.builder().bucket(bucket).key(key).build()).asByteArray();
        if(!hash(bytes).equals(expected)) throw new IllegalStateException("attachment_checksum_mismatch");
        return bytes;
    }
    @Scheduled(fixedDelay=60000) public void cleanup() {
        if(client==null) return;
        independent.executeWithoutResult(s->{
            for(var row:db.queryForList("SELECT object_key FROM object_cleanup WHERE after_at<now() ORDER BY after_at LIMIT 50 FOR UPDATE SKIP LOCKED")) {
                String key=row.get("object_key").toString();
                if(db.queryForObject("SELECT count(*) FROM attachment WHERE object_key=?",Integer.class,key)==0) client.deleteObject(DeleteObjectRequest.builder().bucket(bucket).key(key).build());
                db.update("DELETE FROM object_cleanup WHERE object_key=?",key);
            }
        });
    }
    @Scheduled(fixedDelay=30000) public void migrate() {
        if(client==null) return;
        for(var row:db.queryForList("SELECT id,content,content_type FROM attachment WHERE object_key IS NULL AND content IS NOT NULL LIMIT 10")) {
            byte[] bytes=(byte[])row.get("content"); String key="attachments/"+row.get("id")+"/"+UUID.randomUUID();
            put(key,bytes,row.get("content_type").toString()); String sha=hash(bytes); get(key,sha);
            independent.executeWithoutResult(s->db.update("UPDATE attachment SET object_key=?,sha256=?,content=NULL WHERE id=? AND object_key IS NULL",key,sha,row.get("id")));
        }
    }
    @jakarta.annotation.PreDestroy public void close() { if(client!=null) client.close(); }
}
