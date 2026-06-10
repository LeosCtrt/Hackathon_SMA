"""
Moteur what-if capacité HDJ — simulation greedy journalière.

Calcule planification, attente et occupation pour n'importe quel ensemble
de candidats sans relancer la simulation Mesa complète.
Toutes les durées sont issues du YAML ou d'estimations opérationnelles.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

WORK_MINUTES_PER_DAY = 360  # 6h de capacité HDJ opérationnelle

# Durées opérationnelles par parcours (fallback si YAML indisponible)
_FALLBACK_DURATIONS = {
    "bilan_annuel_diabete": 60,
    "bilan_endocrino_metabolique": 90,
    "etp_diabete_obesite": 90,
    "test_dynamique_endocrinien": 180,
    "depistage_retinopathie": 90,
    "already_hdj": 60,
    "recurrent_grouping": 70,
}

_NEEDS_RETINO = {"depistage_retinopathie"}

_PRIORITY_WEIGHT = {
    "already_hdj": 1,
    "bilan_annuel_diabete": 2,
    "depistage_retinopathie": 3,
    "bilan_endocrino_metabolique": 3,
    "etp_diabete_obesite": 4,
    "test_dynamique_endocrinien": 5,
    "recurrent_grouping": 2,
}

# Distribution réelle issue de la simulation (kpis_B.by_pathway)
SCENARIO_DISTRIBUTIONS: Dict[str, Dict[str, int]] = {
    "baseline_A": {"already_hdj": 5},
    "target_B": {
        "bilan_annuel_diabete": 12,
        "bilan_endocrino_metabolique": 9,
        "test_dynamique_endocrinien": 3,
        "already_hdj": 4,
        "etp_diabete_obesite": 4,
        "depistage_retinopathie": 1,
    },
    "recurrent_grouping": {
        "bilan_annuel_diabete": 50,
        "bilan_endocrino_metabolique": 35,
        "etp_diabete_obesite": 20,
        "depistage_retinopathie": 10,
    },
    "transformation": {
        "bilan_annuel_diabete": 50,
        "bilan_endocrino_metabolique": 35,
        "etp_diabete_obesite": 20,
        "depistage_retinopathie": 10,
    },
}


def _load_yaml_durations() -> Dict[str, int]:
    yaml_path = Path("core/config/hdj_metier.yaml")
    durations = dict(_FALLBACK_DURATIONS)
    try:
        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        actes = cfg["actes_et_taches"]["actes_ccam_hdj_endocrino"]
        mapping = {
            "retinographie": "depistage_retinopathie",
            "bilan_annuel_diabete": "bilan_annuel_diabete",
            "test_dynamique_endocrinien": "test_dynamique_endocrinien",
            "consultation_simple": "already_hdj",
        }
        for yaml_key, pathway_key in mapping.items():
            if yaml_key in actes:
                durations[pathway_key] = int(actes[yaml_key]["duree_min"])
    except Exception:
        pass
    return durations


def generate_scenario_candidates(
    scenario: str = "target_B",
    validation_rate_B: float = 1.0,
    n_override: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Génère une liste de candidats synthétiques (sans IPP) pour un scénario.

    Args:
        scenario         : "baseline_A", "target_B", "recurrent_grouping", "transformation"
        validation_rate_B: fraction de candidats B retenus (0–1)
        n_override       : surcharger le nombre total de candidats

    Returns:
        list de dicts {pathway, duration_min, needs_retinograph, priority_weight}
    """
    durations = _load_yaml_durations()
    distribution = dict(SCENARIO_DISTRIBUTIONS.get(scenario, SCENARIO_DISTRIBUTIONS["target_B"]))

    if n_override is not None:
        total_base = sum(distribution.values())
        if total_base > 0:
            factor = n_override / total_base
            distribution = {k: max(1, round(v * factor)) for k, v in distribution.items()}

    # Appliquer validation_rate_B : réduire les volumes B proportionnellement
    if validation_rate_B < 1.0:
        distribution = {
            k: max(0, math.floor(v * validation_rate_B))
            for k, v in distribution.items()
        }

    candidates = []
    for pathway, count in distribution.items():
        dur = durations.get(pathway, 60)
        for _ in range(count):
            candidates.append({
                "pathway": pathway,
                "duration_min": dur,
                "needs_retinograph": pathway in _NEEDS_RETINO,
                "priority_weight": _PRIORITY_WEIGHT.get(pathway, 3),
            })

    return candidates


def run_capacity_what_if(
    candidates: List[Dict[str, Any]],
    horizon_days: int = 5,
    slots_per_day: int = 6,
    chairs: int = 2,
    retinographs: int = 1,
    validation_rate_B: float = 1.0,
    priority_mode: str = "strategic",
    tariff_per_day: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Simulation greedy de planification HDJ sur horizon_days jours.

    Le résultat varie avec :
    - horizon_days : plus court → plus de cas non planifiés
    - chairs / retinographs : plus de ressources → plus absorbés
    - validation_rate_B : taux de dossiers validés DIM/PMSI
    - priority_mode : ordre d'affectation

    Returns:
        dict avec planned_count, mean_wait_days, occupancy, bottleneck, daily_schedule, etc.
    """
    # Appliquer validation_rate_B
    if validation_rate_B < 1.0:
        n_keep = max(1, math.floor(len(candidates) * validation_rate_B))
        candidates = candidates[:n_keep]

    # Trier selon priorité
    if priority_mode in ("strategic", "priorite_strategique"):
        candidates = sorted(candidates, key=lambda c: (c["priority_weight"], c["duration_min"]))
    elif priority_mode in ("volume", "priorite_volume"):
        candidates = sorted(candidates, key=lambda c: c["duration_min"])  # courts en premier
    elif priority_mode in ("recurrent", "patients_recurrents"):
        candidates = sorted(candidates, key=lambda c: c["priority_weight"])
    else:
        candidates = sorted(candidates, key=lambda c: c["priority_weight"])

    # Capacité journalière
    chair_avail = [chairs * WORK_MINUTES_PER_DAY for _ in range(horizon_days)]
    retino_avail = [retinographs * WORK_MINUTES_PER_DAY for _ in range(horizon_days)]

    assigned: List[Dict] = []
    unplanned: List[Dict] = []

    for c in candidates:
        dur = c["duration_min"]
        needs_retino = c.get("needs_retinograph", False)

        best_day = None
        for d in range(horizon_days):
            chair_ok = chair_avail[d] >= dur
            retino_ok = (not needs_retino) or (retino_avail[d] >= dur)
            if chair_ok and retino_ok:
                best_day = d
                break

        if best_day is not None:
            chair_avail[best_day] -= dur
            if needs_retino:
                retino_avail[best_day] -= dur
            assigned.append({**c, "assigned_day": best_day + 1, "wait_days": best_day})
        else:
            unplanned.append(c)

    # Stats attente
    wait_list = [a["wait_days"] for a in assigned]
    mean_wait = round(sum(wait_list) / len(wait_list), 2) if wait_list else 0.0
    max_wait = max(wait_list) if wait_list else 0

    # Occupation
    total_chair_avail = chairs * WORK_MINUTES_PER_DAY * horizon_days
    total_retino_avail = retinographs * WORK_MINUTES_PER_DAY * horizon_days
    chair_used = sum(a["duration_min"] for a in assigned)
    retino_used = sum(a["duration_min"] for a in assigned if a.get("needs_retinograph"))
    occ_chair = round(chair_used / total_chair_avail * 100, 1) if total_chair_avail else 0.0
    occ_retino = round(retino_used / total_retino_avail * 100, 1) if total_retino_avail else 0.0

    # Goulot
    n_unpl = len(unplanned)
    if n_unpl == 0:
        bottleneck = "Validation organisationnelle / PMSI"
    else:
        retino_unpl = [c for c in unplanned if c.get("needs_retinograph")]
        chair_saturated = chair_used >= total_chair_avail * 0.9
        retino_saturated = retino_used >= total_retino_avail * 0.9
        if horizon_days <= 3 and n_unpl > 0:
            bottleneck = "Horizon de planification trop court"
        elif retino_saturated and retino_unpl:
            bottleneck = "Rétinographe"
        elif chair_saturated:
            bottleneck = "Fauteuil médicalisé"
        else:
            bottleneck = "Horizon de planification"

    # Planning journalier agrégé (sans IPP)
    daily_schedule = []
    for d in range(horizon_days):
        day_a = [a for a in assigned if a["assigned_day"] == d + 1]
        pathway_counts: Dict[str, int] = {}
        for a in day_a:
            pw = a["pathway"]
            pathway_counts[pw] = pathway_counts.get(pw, 0) + 1
        used_min = sum(a["duration_min"] for a in day_a)
        avail_min = chairs * WORK_MINUTES_PER_DAY
        daily_schedule.append({
            "jour": d + 1,
            "sejours_planifies": len(day_a),
            "parcours": pathway_counts,
            "minutes_fauteuil_utilisees": used_min,
            "minutes_fauteuil_disponibles": avail_min,
            "occupation_fauteuil_pct": round(used_min / avail_min * 100, 1) if avail_min else 0,
        })

    # Message décisionnel
    total_cand = len(candidates)
    if n_unpl == 0:
        decision_msg = (
            f"Tous les {len(assigned)} séjours absorbés sur {horizon_days} j. "
            "La capacité matérielle est suffisante — le goulot est la validation DIM/PMSI."
        )
    elif n_unpl <= max(3, total_cand * 0.15):
        decision_msg = (
            f"{len(assigned)}/{total_cand} planifiés — {n_unpl} débordent. "
            f"Étendre l'horizon à {horizon_days + 2} j ou ajouter 1 fauteuil."
        )
    else:
        pct = round(n_unpl / total_cand * 100)
        decision_msg = (
            f"Saturation : {pct}% non planifiés ({n_unpl}/{total_cand}). "
            "Augmenter la capacité (fauteuils/horizon) ou lisser sur plusieurs semaines."
        )

    # Estimation financière indicative
    financial = None
    if tariff_per_day and len(assigned) > 0:
        financial = {
            "volume_planifie": len(assigned),
            "valorisation_indicative_euros": round(len(assigned) * tariff_per_day, 0),
            "tariff_reference": tariff_per_day,
            "note": "Indicatif — non certifié, à valider DIM/PMSI",
        }

    return {
        "parametres": {
            "horizon_jours": horizon_days,
            "fauteuils": chairs,
            "retinographes": retinographs,
            "taux_validation_B": validation_rate_B,
            "mode_priorite": priority_mode,
        },
        "planned_count": len(assigned),
        "unplanned_count": n_unpl,
        "mean_wait_days": mean_wait,
        "max_wait_days": max_wait,
        "occupancy_chair_pct": occ_chair,
        "occupancy_retinograph_pct": occ_retino,
        "bottleneck": bottleneck,
        "daily_schedule": daily_schedule,
        "decision_message": decision_msg,
        "financial_estimate": financial,
        "warnings": (
            ["Simulation greedy déterministe — ne modélise pas les contraintes soignants individuelles"]
            if n_unpl > 0 else []
        ),
        "assumptions": {
            "minutes_travail_par_jour": WORK_MINUTES_PER_DAY,
            "source_durees": "hdj_metier.yaml + estimations opérationnelles",
            "note": "À valider avec l'équipe soignante et le DIM avant mise en œuvre.",
        },
    }


def run_preset_scenarios(
    output_path: str | Path = "outputs/what_if_capacity_results.json",
    daily_output_path: str | Path = "outputs/daily_schedule_example.json",
) -> Dict[str, Any]:
    """
    Lance les 8 configurations préréglées et écrit les fichiers JSON.
    """
    presets = [
        {
            "id": "baseline_A_5_days",
            "label": "Scénario prudent (A) — 5 jours",
            "scenario": "baseline_A",
            "kwargs": {"horizon_days": 5, "chairs": 2, "retinographs": 1, "validation_rate_B": 1.0},
        },
        {
            "id": "target_B_5_days",
            "label": "Réorganisation cible (B) — 5 jours",
            "scenario": "target_B",
            "kwargs": {"horizon_days": 5, "chairs": 2, "retinographs": 1, "validation_rate_B": 1.0},
        },
        {
            "id": "target_B_2_days_stress",
            "label": "Réorganisation cible (B) — stress 2 jours",
            "scenario": "target_B",
            "kwargs": {"horizon_days": 2, "chairs": 2, "retinographs": 1, "validation_rate_B": 1.0},
        },
        {
            "id": "target_B_10_days",
            "label": "Réorganisation cible (B) — horizon 10 jours",
            "scenario": "target_B",
            "kwargs": {"horizon_days": 10, "chairs": 2, "retinographs": 1, "validation_rate_B": 1.0},
        },
        {
            "id": "target_B_plus_chair",
            "label": "Réorganisation cible (B) — +1 fauteuil",
            "scenario": "target_B",
            "kwargs": {"horizon_days": 5, "chairs": 3, "retinographs": 1, "validation_rate_B": 1.0},
        },
        {
            "id": "target_B_plus_retinograph",
            "label": "Réorganisation cible (B) — +1 rétinographe",
            "scenario": "target_B",
            "kwargs": {"horizon_days": 5, "chairs": 2, "retinographs": 2, "validation_rate_B": 1.0},
        },
        {
            "id": "recurrent_grouping_5_days",
            "label": "Regroupement patients récurrents — 5 jours",
            "scenario": "recurrent_grouping",
            "kwargs": {"horizon_days": 5, "chairs": 2, "retinographs": 1, "validation_rate_B": 1.0},
        },
        {
            "id": "recurrent_grouping_10_days",
            "label": "Regroupement patients récurrents — 10 jours",
            "scenario": "recurrent_grouping",
            "kwargs": {"horizon_days": 10, "chairs": 2, "retinographs": 1, "validation_rate_B": 1.0},
        },
    ]

    results = []
    example_daily = None

    for preset in presets:
        cands = generate_scenario_candidates(preset["scenario"])
        result = run_capacity_what_if(cands, **preset["kwargs"])
        entry = {
            "configuration_id": preset["id"],
            "label": preset["label"],
            "scenario_base": preset["scenario"],
            "parametres": result["parametres"],
            "planned_count": result["planned_count"],
            "unplanned_count": result["unplanned_count"],
            "mean_wait_days": result["mean_wait_days"],
            "max_wait_days": result["max_wait_days"],
            "occupancy_chair_pct": result["occupancy_chair_pct"],
            "occupancy_retinograph_pct": result["occupancy_retinograph_pct"],
            "bottleneck": result["bottleneck"],
            "decision_message": result["decision_message"],
        }
        results.append(entry)

        # Garder le planning journalier de target_B_5_days comme exemple
        if preset["id"] == "target_B_5_days":
            example_daily = {
                "analyse": "Planning journalier agrégé — Réorganisation cible (B), 5 jours",
                "note": "Données agrégées — aucun IPP individuel exposé.",
                "parametres": result["parametres"],
                "jours": result["daily_schedule"],
            }

    what_if_output = {
        "analyse": "Simulation what-if capacité HDJ — 8 configurations comparées",
        "note": (
            "Simulation greedy déterministe. Durées issues du YAML métier. "
            "Résultats à valider avec l'équipe soignante et le DIM/PMSI."
        ),
        "configurations": results,
        "interpretation": (
            "Sur le volume B actuel (33 cas), la capacité matérielle est suffisante. "
            "La saturation apparaît lors du regroupement des patients récurrents (115 cas) "
            "ou en horizon court (2 jours). Le goulot principal reste la validation DIM/PMSI."
        ),
    }

    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(what_if_output, ensure_ascii=False, indent=2), encoding="utf-8")

    if example_daily:
        dl = Path(daily_output_path)
        dl.write_text(json.dumps(example_daily, ensure_ascii=False, indent=2), encoding="utf-8")

    return what_if_output
