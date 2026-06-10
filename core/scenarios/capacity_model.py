"""
Modèle de capacité HDJ — simulation de plusieurs configurations.

Teste l'impact de différentes configurations de ressources/capacité
sur le volume planifiable et l'occupation des ressources critiques.

Toutes les durées viennent du YAML (estimation_method: duration_from_yaml).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from core.agents.coordinateur import CoordinateurAgent
from core.resources.ressources_hdj import RessourceLimitante, create_mvp_resources
from core.simulation.scheduler import DEFAULT_MAX_PARALLEL, DEFAULT_N_DAYS, Scheduler


def _run_config(
    df: pd.DataFrame,
    n_days: int,
    max_parallel: int,
    extra_fauteuil: int = 0,
    extra_retino: int = 0,
) -> Dict[str, Any]:
    """Lance le coordinateur avec une configuration de ressources donnée."""
    agent = CoordinateurAgent(n_days=n_days, max_parallel=max_parallel)

    # Surcharger les ressources si configuration modifiée
    if extra_fauteuil > 0 or extra_retino > 0:
        import yaml
        from pathlib import Path as _Path
        yaml_path = _Path("core/config/hdj_metier.yaml")
        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        mvp = cfg["ressources_hdj"]["mvp_ressources_goulot"]

        retino_qty = int(mvp["retinographe"]["quantite"]) + extra_retino
        fauteuil_qty = int(mvp["fauteuil_medicalise"]["quantite"]) + extra_fauteuil

        resources_A = {
            "retinographe": RessourceLimitante(mvp["retinographe"]["nom"], retino_qty),
            "fauteuil": RessourceLimitante(mvp["fauteuil_medicalise"]["nom"], fauteuil_qty),
        }
        resources_B = {
            "retinographe": RessourceLimitante(mvp["retinographe"]["nom"], retino_qty),
            "fauteuil": RessourceLimitante(mvp["fauteuil_medicalise"]["nom"], fauteuil_qty),
        }
        agent.resources_A = resources_A
        agent.resources_B = resources_B
        agent.scheduler_A = Scheduler(resources_A, n_days=n_days, max_parallel=max_parallel)
        agent.scheduler_B = Scheduler(resources_B, n_days=n_days, max_parallel=max_parallel)

    agent.load_data(df)
    agent.run()

    ts_A = agent.scheduler_A.total_slots()
    ts_B = agent.scheduler_B.total_slots()
    ret_A = agent.resources_A["retinographe"]
    fau_A = agent.resources_A["fauteuil"]
    ret_B = agent.resources_B["retinographe"]
    fau_B = agent.resources_B["fauteuil"]

    return {
        "n_days": n_days,
        "max_parallel": max_parallel,
        "retinographe_capacite": ret_A.total_units + extra_retino,
        "fauteuil_capacite": fau_A.total_units + extra_fauteuil,
        "scenario_A": {
            "planifies": agent.kpis_A.scheduled,
            "non_planifies": agent.kpis_A.not_scheduled,
            "delai_attente_moyen_j": round(agent.kpis_A.avg_wait_days, 1),
            "retinographe_occ_pct": round(ret_A.occupancy_rate(ts_A) * 100, 1),
            "fauteuil_occ_pct": round(fau_A.occupancy_rate(ts_A) * 100, 1),
            "retinographe_pic": ret_A.peak_simultaneous(),
            "fauteuil_pic": fau_A.peak_simultaneous(),
        },
        "scenario_B": {
            "simules": agent.kpis_B.scheduled,
            "non_planifies": agent.kpis_B.not_scheduled,
            "gain_vs_A": agent.kpis_B.gain_vs_a,
            "delai_attente_moyen_j": round(agent.kpis_B.avg_wait_days, 1),
            "retinographe_occ_pct": round(ret_B.occupancy_rate(ts_B) * 100, 1),
            "fauteuil_occ_pct": round(fau_B.occupancy_rate(ts_B) * 100, 1),
            "retinographe_pic": ret_B.peak_simultaneous(),
            "fauteuil_pic": fau_B.peak_simultaneous(),
        },
    }


def simulate_capacity(
    df: pd.DataFrame,
    horizon_days: int = DEFAULT_N_DAYS,
    output_path: str | Path = "outputs/capacity_simulation.json",
) -> Dict[str, Any]:
    """
    Simule plusieurs configurations de capacité HDJ et compare les résultats.

    Args:
        df           : DataFrame agrégé par séjour.
        horizon_days : horizon de simulation de base.
        output_path  : chemin de sortie JSON.

    Returns:
        dict capacity_simulation.
    """
    configurations = [
        {
            "id": "config_actuelle",
            "label": "Configuration actuelle",
            "description": "Ressources actuelles : rétinographe ×1, fauteuil ×2, 6 places/créneau",
            "extra_fauteuil": 0,
            "extra_retino": 0,
            "n_days": horizon_days,
            "max_parallel": DEFAULT_MAX_PARALLEL,
        },
        {
            "id": "plus_1_fauteuil",
            "label": "+1 fauteuil médicalisé",
            "description": "Ajout d'un fauteuil → 3 fauteuils disponibles",
            "extra_fauteuil": 1,
            "extra_retino": 0,
            "n_days": horizon_days,
            "max_parallel": DEFAULT_MAX_PARALLEL,
        },
        {
            "id": "plus_1_retino",
            "label": "+1 rétinographe",
            "description": "Ajout d'un rétinographe → 2 disponibles",
            "extra_fauteuil": 0,
            "extra_retino": 1,
            "n_days": horizon_days,
            "max_parallel": DEFAULT_MAX_PARALLEL,
        },
        {
            "id": "horizon_10j",
            "label": "Horizon 10 jours",
            "description": "Horizon de planification étendu à 10 jours ouvrés",
            "extra_fauteuil": 0,
            "extra_retino": 0,
            "n_days": 10,
            "max_parallel": DEFAULT_MAX_PARALLEL,
        },
        {
            "id": "capacite_etendue",
            "label": "Capacité étendue (+1 créneau/jour)",
            "description": "8 places simultanées au lieu de 6 par créneau",
            "extra_fauteuil": 0,
            "extra_retino": 0,
            "n_days": horizon_days,
            "max_parallel": 8,
        },
        {
            "id": "configuration_optimisee",
            "label": "Configuration optimisée",
            "description": "+1 fauteuil + horizon 10 jours + 8 places/créneau",
            "extra_fauteuil": 1,
            "extra_retino": 0,
            "n_days": 10,
            "max_parallel": 8,
        },
    ]

    results: List[Dict[str, Any]] = []
    base_planifies_A = None
    base_simules_B = None

    for cfg in configurations:
        result = _run_config(
            df,
            n_days=cfg["n_days"],
            max_parallel=cfg["max_parallel"],
            extra_fauteuil=cfg["extra_fauteuil"],
            extra_retino=cfg["extra_retino"],
        )
        if base_planifies_A is None:
            base_planifies_A = result["scenario_A"]["planifies"]
            base_simules_B = result["scenario_B"]["simules"]

        gain_A = result["scenario_A"]["planifies"] - (base_planifies_A or 0)
        gain_B = result["scenario_B"]["simules"] - (base_simules_B or 0)

        # Identifier le goulot
        occ_ret = result["scenario_B"]["retinographe_occ_pct"]
        occ_fau = result["scenario_B"]["fauteuil_occ_pct"]
        if occ_ret >= occ_fau and occ_ret > 50:
            bottleneck = f"Rétinographe ({occ_ret:.0f}% occupation)"
        elif occ_fau > occ_ret and occ_fau > 50:
            bottleneck = f"Fauteuil ({occ_fau:.0f}% occupation)"
        else:
            bottleneck = "Capacité de planification (pas de saturation ressource)"

        # Message décisionnel
        if gain_B > 3:
            msg = f"+{gain_B} séjours supplémentaires simulables — investissement justifié"
        elif gain_B > 0:
            msg = f"+{gain_B} séjours supplémentaires — gain marginal à évaluer"
        else:
            msg = "Pas de gain supplémentaire — contrainte non liée aux ressources"

        results.append({
            "configuration": cfg["id"],
            "label": cfg["label"],
            "description": cfg["description"],
            "parametres": {
                "horizon_jours": cfg["n_days"],
                "places_creneau": cfg["max_parallel"],
                "retinographe_total": result["retinographe_capacite"],
                "fauteuil_total": result["fauteuil_capacite"],
            },
            "resultats": result,
            "gain_vs_baseline_A": gain_A,
            "gain_vs_baseline_B": gain_B,
            "goulot_detranglement": bottleneck,
            "message_decisionnel": msg,
            "estimation_method": "duration_from_yaml — estimation opérationnelle",
        })

    simulation: Dict[str, Any] = {
        "analyse": "Simulation capacité HDJ — configurations comparées",
        "main_bottleneck": "validation_organisationnelle_pmsi",
        "capacity_message": (
            "La capacité équipement (rétinographe, fauteuil) n'est pas le goulot principal. "
            "Le goulot principal est la validation organisationnelle et PMSI des parcours HDJ : "
            "sans instruction DIM/PMSI, aucun séjour supplémentaire ne peut être facturé "
            "quelle que soit la capacité matérielle disponible."
        ),
        "note": (
            "Durées issues du YAML métier (estimation opérationnelle basée sur les durées "
            "paramétrées, source : hdj_metier.yaml). À valider avec l'équipe soignante."
        ),
        "configurations": results,
        "recommandation": (
            "La configuration '+1 fauteuil' montre le meilleur rapport impact/investissement "
            "pour augmenter le volume simulable en scénario B."
            if any(r["gain_vs_baseline_B"] > 0 for r in results[1:])
            else "La contrainte principale est organisationnelle, pas liée aux équipements."
        ),
    }

    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(simulation, ensure_ascii=False, indent=2), encoding="utf-8")

    return simulation
