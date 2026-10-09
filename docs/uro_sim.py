"""거리 기반 애니메이션 갱신 주기 시뮬레이션.

게임 코드(5cf52376)의 판단 로직을 그대로 옮겼다.
  - CMonster::Calc_AnimPeriod : 렌더 컬링 → 8, 표면 거리 >= 80 → 4, >= 65 → 2, 그 외 1  (s_iPeriodB)
  - CMonster::Update_CullGrade : 프레임 카운터 + 생성 시 위상(rand() % 8), 건너뛴 dt 누적 후 갱신 프레임에 전달
  - Evaluate_DistanceFade      : 표면 거리 >= 컬링 거리(175) 면 렌더 컬링
기준선은 s_bUseAnimURO = false 와 같은 '모든 구간 매 프레임 갱신' (s_iPeriodA = 1,1,1,1).
측정값은 CPU 시간이 아니라 Animator 갱신 호출 횟수다.
"""
import random, json, sys

CULL_DIST = 175.0
BAND_HALF = 65.0
BAND_QUARTER = 80.0
PERIOD_B = (1, 2, 4, 8)
PERIOD_A = (1, 1, 1, 1)


def calc_period(dist, uro=True):
    P = PERIOD_B if uro else PERIOD_A
    if dist >= CULL_DIST:
        return P[3]
    if dist >= BAND_QUARTER:
        return P[2]
    if dist >= BAND_HALF:
        return P[1]
    return P[0]


class Monster:
    def __init__(self, dist, phase):
        self.dist = dist
        self.phase = phase
        self.frame = 0
        self.accum = 0.0
        self.animated = 0.0      # Animator 에 실제로 전달된 시간 합

    def tick(self, dt, uro=True, accumulate=True):
        period = calc_period(self.dist, uro)
        self.accum += dt
        self.frame += 1
        anim_tick = period <= 1 or (self.frame + self.phase) % period == 0
        if anim_tick:
            self.animated += self.accum if accumulate else dt
            self.accum = 0.0
        return anim_tick


def run(dists, frames, uro=True, phases=None, dt=1 / 60, accumulate=True):
    ms = [Monster(d, phases[i] if phases else 0) for i, d in enumerate(dists)]
    per_frame = []
    for _ in range(frames):
        per_frame.append(sum(m.tick(dt, uro, accumulate) for m in ms))
    return per_frame, ms


def main(out):
    rnd = random.Random(7)
    N, F = 30, 240                      # 30마리, 240프레임(60fps 4초)
    res = {}

    # 1) 카메라가 몬스터 무리에서 멀어질 때 (무리는 카메라 앞 0 ~ 60 범위에 고르게 배치)
    base = [rnd.uniform(0, 60) for _ in range(N)]
    phases = [rnd.randrange(8) for _ in range(N)]
    sweep = []
    for off in range(0, 201, 10):
        d = [b + off for b in base]
        a, _ = run(d, F, uro=False, phases=phases)
        b, _ = run(d, F, uro=True, phases=phases)
        sweep.append(dict(offset=off, base=sum(a) / F, uro=sum(b) / F,
                          bands=[sum(1 for x in d if calc_period(x) == p) for p in PERIOD_B]))
    res['sweep'] = sweep

    # 2) 위상 분산: 30마리 모두 컬링 밖(주기 8)
    far = [200.0] * N
    with_phase, _ = run(far, 16, uro=True, phases=[rnd.randrange(8) for _ in range(N)])
    no_phase, _ = run(far, 16, uro=True, phases=[0] * N)
    res['phase'] = dict(with_phase=with_phase, no_phase=no_phase)

    # 3) 시간 누적: 주기 8 몬스터 1마리, 600프레임 (가변 dt)
    dts = [rnd.uniform(1 / 75, 1 / 45) for _ in range(600)]
    m_acc = Monster(200.0, 3)
    m_skip = Monster(200.0, 3)
    for dt in dts:
        m_acc.tick(dt, True, True)
        m_skip.tick(dt, True, False)
    res['accum'] = dict(elapsed=sum(dts), animated_accum=m_acc.animated, pending=m_acc.accum,
                        animated_skip=m_skip.animated)

    if out:
        json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('[1] 카메라 거리 스윕 (30마리, 프레임당 평균 갱신 수)')
    for r in sweep[::2]:
        print(f"  +{r['offset']:3}  기준 {r['base']:5.1f}  주기조절 {r['uro']:5.2f}  ({r['uro']/r['base']*100:5.1f}%)  구간별 {r['bands']}")
    print(f"[2] 위상 분산 (주기 8, 30마리) 위상 있음: {with_phase}")
    print(f"                              위상 없음: {no_phase}")
    ac = res['accum']
    print(f"[3] 경과 {ac['elapsed']:.3f}s / 누적 전달 {ac['animated_accum']:.3f}s (+대기 {ac['pending']:.3f}s) / 누적 없이 {ac['animated_skip']:.3f}s")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
