# Official multi-platform Python 3.14.8 / Alpine 3.24 image, verified on 2026-10-08.
FROM python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

ARG RELEASE_COMMIT=local
LABEL org.opencontainers.image.title="Asteri Deployment Lab" \
      org.opencontainers.image.description="Temporary static university deployment exercise" \
      org.opencontainers.image.revision="${RELEASE_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=qa \
    PORT=8080 \
    RELEASE_COMMIT=${RELEASE_COMMIT}

# Apply available Alpine security updates. This application uses only Python's
# standard library, so remove pip and its bundled third-party packages, including
# ensurepip's reinstallable wheels, from the final filesystem.
RUN apk upgrade --no-cache \
    && python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip \
    && python -c "import importlib.util; assert importlib.util.find_spec('pip') is None"

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
