# Lambda 컨테이너 이미지 빌드
# 베이스: AWS 공식 Python 3.12 Lambda 런타임
FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

# 의존성 먼저 복사 (레이어 캐시 활용)
COPY pyproject.toml ./
RUN pip install --no-cache-dir "." --target "${LAMBDA_TASK_ROOT}"

# 소스 복사
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY alembic/ ${LAMBDA_TASK_ROOT}/alembic/
COPY alembic.ini ${LAMBDA_TASK_ROOT}/alembic.ini

# Lambda 핸들러 진입점
CMD ["app.lambda_handler.handler"]
