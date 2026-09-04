from typing import Any

_INJURY_RULES: dict[str, dict[str, str]] = {
    "knee": {
        "caution": (
            "INJURY_KNEE_CAUTION: 무릎 주의 — 내리막 인터벌 금지, 충격 최소화."
            " 트레드밀이나 평지 우선."
        ),
        "severe": (
            "INJURY_KNEE_SEVERE: 무릎 심각 — 러닝 중단 권고."
            " 수영·자전거 등 비충격 유산소 추천. 전문의 상담 안내."
        ),
    },
    "ankle": {
        "caution": (
            "INJURY_ANKLE_CAUTION: 발목 주의 — 트레일/울퉁불퉁한 노면 회피. 평지 이지런 위주."
        ),
        "severe": "INJURY_ANKLE_SEVERE: 발목 심각 — 러닝 중단 권고. 전문의 상담 안내.",
    },
    "achilles": {
        "caution": (
            "INJURY_ACHILLES_CAUTION: 아킬레스건 주의 — 스피드워크 제한, 페이스 10-15% 하향."
            " 힐드롭 스트레칭 포함."
        ),
        "severe": "INJURY_ACHILLES_SEVERE: 아킬레스건 심각 — 러닝 중단 권고. 전문의 상담 안내.",
    },
    "shin": {
        "caution": (
            "INJURY_SHIN_CAUTION: 정강이(신스플린트) 주의 — 볼륨 50% 감소, 이지런 only,"
            " 부드러운 노면 추천."
        ),
        "severe": "INJURY_SHIN_SEVERE: 정강이 심각 — 러닝 중단 권고. 전문의 상담 안내.",
    },
    "hip_back": {
        "caution": (
            "INJURY_HIP_CAUTION: 허리/고관절 주의 — 페이스워크 중심, 스트라이드 줄이기."
            " 코어 강화 운동 제안."
        ),
        "severe": "INJURY_HIP_SEVERE: 허리/고관절 심각 — 러닝 중단 권고. 전문의 상담 안내.",
    },
    "plantar_fascia": {
        "caution": (
            "INJURY_PF_CAUTION: 족저근막 주의 — 스피드워크 제한, 쿠셔닝 좋은 신발 안내."
            " 아침 첫 러닝 주의."
        ),
        "severe": "INJURY_PF_SEVERE: 족저근막 심각 — 러닝 중단 권고. 전문의 상담 안내.",
    },
}

_INJURY_PART_KR: dict[str, str] = {
    "knee": "무릎",
    "ankle": "발목",
    "achilles": "아킬레스건",
    "shin": "정강이",
    "hip_back": "허리/고관절",
    "plantar_fascia": "족저근막",
}


def evaluate_profile_rules(context: dict[str, Any]) -> list[dict[str, str]]:
    """프로필 기반 결정론적 제약을 {"code","message"} dict 리스트로 반환."""
    profile = context.get("runner_profile")
    if not profile:
        return []

    results: list[dict[str, str]] = []

    # ── 경험 레벨 (기존 BEGINNER_GUARD 대체 통합) ──
    level = profile.get("experience_level")
    if level == "beginner":
        results.append(
            {
                "code": "PROFILE_BEGINNER_GUARD",
                "message": (
                    "초보 러너 — 최대 5km, 이지런 위주, 인터벌·템포런 금지. "
                    "용어를 쉽게 풀어 설명할 것."
                ),
            }
        )
    elif level == "novice":
        results.append(
            {
                "code": "PROFILE_NOVICE_LIMIT",
                "message": (
                    "초급 러너 — 최대 8km, 인터벌 주 1회 제한. "
                    "페이스 가이드를 구체적으로 제공할 것."
                ),
            }
        )

    # ── 시간 제약 ──
    time_budget = profile.get("time_per_session")
    if time_budget == "under_30min":
        results.append(
            {
                "code": "PROFILE_TIME_SHORT",
                "message": (
                    "1회 30분 이하 — 장거리(10km+) 추천 금지,"
                    " 짧은 인터벌이나 4km 이하 템포런 추천."
                ),
            }
        )
    elif time_budget == "30_60min":
        results.append(
            {
                "code": "PROFILE_TIME_MEDIUM",
                "message": "1회 30~60분 — 최대 8~10km 세션 구성.",
            }
        )

    # ── 가용 요일 ──
    if not context.get("is_available_day", True):
        results.append(
            {
                "code": "PROFILE_NON_TRAINING_DAY",
                "message": (
                    "오늘은 러닝 예정일이 아님 — 완전 휴식 또는"
                    " 가벼운 선택 러닝(3km 이지런 이하)만 제안."
                    " 사용자가 원하면 뛸 수 있다고 안내."
                ),
            }
        )

    # ── 병행 운동 ──
    cross = profile.get("cross_training", [])
    if "weight" in cross or "boxing" in cross:
        results.append(
            {
                "code": "PROFILE_CROSS_HIGH_LOAD",
                "message": (
                    "근력/복싱 병행 중 — 하체 고강도 훈련 다음날이면 이지런 권장. "
                    "주간 총 운동 부하를 고려하여 러닝 볼륨 20-30% 감소."
                ),
            }
        )
    if "cycling" in cross or "swimming" in cross:
        results.append(
            {
                "code": "PROFILE_CROSS_CARDIO",
                "message": (
                    "자전거/수영 병행 중 — 유산소 베이스 충분."
                    " 러닝은 스피드·주력 향상에 집중 가능."
                ),
            }
        )
    if "yoga" in cross:
        results.append(
            {
                "code": "PROFILE_CROSS_FLEXIBILITY",
                "message": "요가 병행 중 — 유연성·코어 보강됨. 러닝 쿨다운 스트레칭 간소화 가능.",
            }
        )
    if "hiking" in cross:
        results.append(
            {
                "code": "PROFILE_CROSS_HIKING",
                "message": (
                    "등산 병행 중 — 등산 다음날 장거리/고강도 회피."
                    " 주말 등산 시 러닝 볼륨 조절."
                ),
            }
        )

    # ── 부상 ──
    injuries = profile.get("injuries", {})
    mild_parts: list[str] = []

    for part, status in injuries.items():
        if status in ("caution", "severe") and part in _INJURY_RULES:
            results.append(
                {
                    "code": f"INJURY_{part.upper()}_{status.upper()}",
                    "message": _INJURY_RULES[part][status],
                }
            )
        elif status == "mild":
            mild_parts.append(part)

    if mild_parts:
        names = ", ".join(_INJURY_PART_KR.get(p, p) for p in mild_parts)
        results.append(
            {
                "code": "PROFILE_INJURY_MILD_NOTE",
                "message": (
                    f"{names} 경미한 불편 — "
                    "세션 중 통증 시 즉시 중단 안내. 워밍업에 해당 부위 동적 스트레칭 포함."
                ),
            }
        )

    return results
