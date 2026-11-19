# VouchAI official check image.
#
# No dependencies: the core and the check use the Python standard library only,
# so the image has no RUN steps and builds without network access.
# Build platform: linux/amd64 and linux/arm64 (multi-arch base image).
# TODO(phase 5): pin the base image by its multi-arch index digest; CI prints it.
FROM python:3.11-slim

ENV PYTHONHASHSEED=0 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    VOUCHAI_JOBS=2

WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE episodes.jsonl trajectories.jsonl /app/
COPY vouchai /app/vouchai
COPY vouchai_verify /app/vouchai_verify
COPY tests /app/tests
COPY schemas /app/schemas
COPY episodes /app/episodes

# Unprivileged user. The environment and grader run in a child process of the
# caller (VouchAIEnv); separate OS users per zone are listed in docs/LIMITATIONS.md.
USER 10001:10001

ENTRYPOINT ["python", "-m", "vouchai"]
CMD ["check"]
