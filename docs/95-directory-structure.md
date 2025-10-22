
# 95 — Directory Structure (Monorepo)

```
repo/
  apps/
    ui/
    api/
    workers/{ingest,transcode,asr,nlp,subtitle,tts,render,retell,export,billing,common}
  packages/{shared-schemas,shared-utils}
  infra/{docker,k8s,nginx}
  .github/workflows/
```
