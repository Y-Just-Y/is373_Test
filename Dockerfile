# Official multi-platform Python 3.14.8 slim image, verified on 2026-10-08.
FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2

ARG RELEASE_COMMIT=local
LABEL org.opencontainers.image.title="Asteri Deployment Lab" \
      org.opencontainers.image.description="Temporary static university deployment exercise" \
      org.opencontainers.image.revision="${RELEASE_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=qa \
    PORT=8080 \
    RELEASE_COMMIT=${RELEASE_COMMIT}

WORKDIR /app
COPY --chown=0:0 app/ ./app/
COPY --chown=0:0 site/ ./site/

# A numeric identity needs no extra packages or mutable user-home directory.
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import json,os,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health',timeout=2); assert r.status==200 and json.load(r)['status']=='ok'"]
STOPSIGNAL SIGTERM
CMD ["python", "-m", "app.main"]
