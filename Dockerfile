# VouchAI official check image.
#
# No dependencies: the core and the check use the Python standard library only,
# so the image has no RUN steps and builds without network access.
# Build platform: linux/amd64 and linux/arm64 (multi-arch base image).
# Pinned by its multi-arch index digest (CI prints the current one).
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

ENV PYTHONHASHSEED=0 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOME=/tmp

WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE CHANGELOG.md Dockerfile episodes.jsonl trajectories.jsonl judge_adapter.py /app/
COPY vouchai /app/vouchai
COPY vouchai_verify /app/vouchai_verify
COPY vouchai_learn /app/vouchai_learn
COPY sft /app/sft
COPY tests /app/tests
COPY schemas /app/schemas
COPY docs /app/docs
COPY reports /app/reports
COPY episodes /app/episodes
COPY examples /app/examples
COPY recipes /app/recipes

# Unprivileged user. The environment and grader run in a child process of the
# caller (VouchAIEnv); separate OS users per zone are listed in docs/LIMITATIONS.md.
USER 10001:10001

ENTRYPOINT ["python", "-m", "vouchai"]
CMD ["check"]
