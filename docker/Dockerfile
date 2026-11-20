# Enterprise Experts - deterministic assessment runner.
# Contains only the dependency-free engine. It does not contain Claude, the
# project's toolchains (node, go, ...) or any credentials.
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin auditor \
    && mkdir /project /reports && chown auditor:auditor /reports
COPY skills/enterprise-experts/scripts /opt/enterprise-experts
USER 10001:10001
WORKDIR /reports
ENTRYPOINT ["python", "/opt/enterprise-experts/enterprise_experts.py"]
CMD ["discover", "/project", "--out", "/reports"]
