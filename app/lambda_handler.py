from mangum import Mangum

from app.main import create_app

# AWS Lambda 진입점.
# 마이그레이션은 배포 파이프라인에서 `alembic upgrade head`로 별도 실행.
handler = Mangum(create_app(), lifespan="auto")
