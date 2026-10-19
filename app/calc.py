"""Расчёт цепочки шагов формулы (без внешних зависимостей, массы в кг).

На каждом шаге:
  1. разбираем step_key как уравнение реакции и проверяем баланс;
  2. массы реагентов берём из in_data, а если реагент - step_value предыдущего шага,
     то берём рассчитанную массу (так шаги соединяются в цепочку; побочные
     продукты предыдущего шага дальше не передаются);
  3. лимитирующий реагент = min(кмоль / коэффициент); теор. масса продуктов по нему;
  4. практическая масса = теор. масса * произведение constant;
  5. сравниваем с ожиданием пользователя (out_data[step_value]).
"""
import re
from collections import Counter

ATOMIC = {
    "H": 1.008, "Li": 6.94, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06,
    "Cl": 35.45, "K": 39.098, "Ca": 40.078, "Ti": 47.867, "Cr": 51.996, "Mn": 54.938,
    "Fe": 55.845, "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38, "Br": 79.904,
    "Ag": 107.868, "I": 126.904, "Ba": 137.327, "Pb": 207.2,
}
_TOKEN = re.compile(r"([A-Z][a-z]?|\(|\))(\d*)")


def parse_formula(formula: str) -> Counter:
    """Формула вещества; гидраты записываются через * или ·: CaSO4*2H2O."""
    s = formula.replace(" ", "")
    if re.search(r"[*·•]", s):
        total = Counter()
        for part in re.split(r"[*·•]", s):
            m = re.match(r"^(\d+)(.+)$", part)
            mult, body = (int(m.group(1)), m.group(2)) if m else (1, part)
            for k, v in _parse_simple(body).items():
                total[k] += v * mult
        return total
    return _parse_simple(s)


def _parse_simple(formula: str) -> Counter:
    s = formula.replace(" ", "")
    if not s:
        raise ValueError("пустая формула вещества")
    stack, i = [Counter()], 0
    while i < len(s):
        m = _TOKEN.match(s, i)
        if not m:
            raise ValueError(f"не могу разобрать '{formula}' (позиция {i})")
        sym, num = m.group(1), m.group(2)
        n = int(num) if num else 1
        i = m.end()
        if sym == "(":
            stack.append(Counter())
        elif sym == ")":
            if len(stack) == 1:
                raise ValueError(f"лишняя ')' в '{formula}'")
            top = stack.pop()
            for k, v in top.items():
                stack[-1][k] += v * n
        else:
            if sym not in ATOMIC:
                raise ValueError(f"неизвестный элемент '{sym}' в '{formula}'")
            stack[-1][sym] += n
    if len(stack) != 1:
        raise ValueError(f"не закрыта '(' в '{formula}'")
    return stack[0]


def molar_mass(formula: str) -> float:
    """г/моль = кг/кмоль"""
    return sum(ATOMIC[e] * n for e, n in parse_formula(formula).items())


def _side(text: str) -> list[tuple[int, str]]:
    out = []
    for term in text.split("+"):
        m = re.match(r"^(\d+)?\s*(.+)$", term.strip())
        if not m or not m.group(2).strip():
            raise ValueError(f"пустой член уравнения в '{text}'")
        out.append((int(m.group(1) or 1), m.group(2).strip()))
    return out


def parse_equation(eq: str):
    parts = re.split(r"-{1,2}>|→|=", eq)
    if len(parts) != 2:
        raise ValueError(f"ожидается вид 'A + B -> C', получено '{eq}'")
    return _side(parts[0]), _side(parts[1])


def check_balance(eq: str) -> dict:
    left, right = parse_equation(eq)
    cl, cr = Counter(), Counter()
    for c, f in left:
        for e, n in parse_formula(f).items():
            cl[e] += c * n
    for c, f in right:
        for e, n in parse_formula(f).items():
            cr[e] += c * n
    diff = {e: cl[e] - cr[e] for e in set(cl) | set(cr) if cl[e] != cr[e]}
    return {"ok": not diff, "diff": diff}


def _cycle(steps, inputs, const_override, scale, use_constants, tolerance_pct):
    carried: dict[str, float] = {}
    results = []
    for idx, st in enumerate(steps):
        n, eq = st["step"], st["step_key"]
        left, right = parse_equation(eq)
        bal = check_balance(eq)
        if not bal["ok"]:
            raise ValueError(f"шаг {n}: уравнение '{eq}' не сбалансировано {bal['diff']}")

        stored = dict(st.get("in_data") or {})
        if idx == 0 and inputs:
            reagents = {f for _, f in left}
            if unknown := set(inputs) - reagents:
                raise ValueError(f"inputs: {sorted(unknown)} - не реагенты шага {n} ({sorted(reagents)})")
            stored.update(inputs)

        use = {}
        for c, f in left:
            if f in carried:
                use[f] = carried[f]
            elif f in stored:
                use[f] = float(stored[f])
            else:
                raise ValueError(f"шаг {n}: нет массы реагента '{f}' (кг) в in_data")

        ratios = {f: use[f] / molar_mass(f) / c for c, f in left}   # кмоль реакции
        limiting = min(ratios, key=ratios.get)
        xi = ratios[limiting]
        excess = {f: round(use[f] - xi * c * molar_mass(f), 4) for c, f in left if f != limiting}
        theor = {f: xi * c * molar_mass(f) for c, f in right}

        product = st["step_value"].strip()
        if product not in theor:
            raise ValueError(f"шаг {n}: step_value '{product}' не среди продуктов {sorted(theor)}")

        consts = dict(st.get("constant") or {})
        for k in consts:
            if k in const_override:
                consts[k] = const_override[k]
        factor = 1.0
        if use_constants:
            for v in consts.values():
                factor *= v * scale
        practical = {f: m * factor for f, m in theor.items()}

        expected = (st.get("out_data") or {}).get(product)
        deviation = quality = None
        if expected:
            deviation = (practical[product] - expected) / expected * 100
            quality = max(0.0, 1 - abs(deviation) / tolerance_pct)

        warnings = []
        if use_constants and factor > 1 + 1e-9:
            warnings.append(f"шаг {n}: произведение констант = {factor:.4g} > 1, практическая масса "
                            "получается больше теоретической - проверьте constant")
        results.append({
            "step": n, "equation": eq, "warnings": warnings, "product": product, "limiting": limiting,
            "inputs_kg": {f: round(v, 4) for f, v in use.items()},
            "unreacted_kg": excess,
            "theoretical_kg": {f: round(v, 4) for f, v in theor.items()},
            "constants": consts, "factor": round(factor, 6),
            "practical_kg": {f: round(v, 4) for f, v in practical.items()},
            "expected_kg": expected,
            "deviation_pct": None if deviation is None else round(deviation, 2),
            "quality": None if quality is None else round(quality, 3),
        })
        carried = {product: practical[product]}   # дальше по цепочке идёт только step_value
    return results


def run_formula(steps, inputs=None, constants=None, spread_pct=0.0, tolerance_pct=10.0):
    """steps: [{"step","step_key","step_value","in_data","out_data","constant"}, ...]"""
    if not steps:
        raise ValueError("у формулы нет шагов")
    steps = sorted(steps, key=lambda s: s["step"])
    co = constants or {}
    nominal = _cycle(steps, inputs, co, 1.0, True, tolerance_pct)
    ideal = _cycle(steps, inputs, co, 1.0, False, tolerance_pct)
    product = nominal[-1]["product"]
    final = nominal[-1]["practical_kg"][product]
    final_theor = ideal[-1]["practical_kg"][product]
    qualities = [s["quality"] for s in nominal if s["quality"] is not None]
    res = {
        "final_product": product,
        "final_mass_kg": round(final, 4),
        "final_theoretical_kg": round(final_theor, 4),
        "total_yield_pct": round(final / final_theor * 100, 2) if final_theor else None,
        "quality": min(qualities) if qualities else None,
        "quality_basis": f"совпадение с ожиданием пользователя (out_data), допуск {tolerance_pct}%; "
                         "1.0 - точное совпадение, 0 - отклонение не меньше допуска",
        "warnings": [w for st in nominal for w in st["warnings"]],
        "steps": nominal,
    }
    if spread_pct > 0:
        s = spread_pct / 100
        lo = _cycle(steps, inputs, co, 1 - s, True, tolerance_pct)[-1]["practical_kg"][product]
        hi = _cycle(steps, inputs, co, 1 + s, True, tolerance_pct)[-1]["practical_kg"][product]
        res["spread_pct"] = spread_pct
        res["final_mass_range_kg"] = [round(min(lo, hi), 4), round(max(lo, hi), 4)]
    return res
