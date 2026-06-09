"""
Export des KPIs HDJ Agent vers JSON/CSV — dashboard Lovable / jury.

Génère dans outputs/ :
  kpi_summary.json              — tous les KPIs (JSON imbriqué)
  kpi_summary.csv               — version plate pour tableur
  scenario_comparison.json      — tableau A vs B
  scenario_comparison.csv       — idem CSV
  patients_recurrents_summary.csv — métriques IPP si disponibles

Usage : python export_dashboard_outputs.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from demo_coordinateur import load_data, aggregate_by_sejour, compute_ipp_metrics
from core.agents.coordinateur import CoordinateurAgent
from core.simulation.scheduler import DEFAULT_N_DAYS, DEFAULT_MAX_PARALLEL


def main() -> None:
    out = Path("outputs")
    out.mkdir(exist_ok=True)

    print("\n=== HDJ Agent — Export Dashboard ===\n")

    # Chargement
    df_raw = load_data("toutes")
    ipp_metrics = compute_ipp_metrics(df_raw)
    if ipp_metrics.get("has_ipp"):
        print(f"[INFO] IPP actif — {ipp_metrics['ipp_uniques']} patients uniques\n")
    df = aggregate_by_sejour(df_raw)

    # Simulation
    agent = CoordinateurAgent(n_days=DEFAULT_N_DAYS, max_parallel=DEFAULT_MAX_PARALLEL)
    agent.load_data(df)
    agent.run()

    # Métriques ressources
    ts_A = agent.scheduler_A.total_slots()
    ts_B = agent.scheduler_B.total_slots()
    ret_A = agent.resources_A["retinographe"]
    fau_A = agent.resources_A["fauteuil"]
    ret_B = agent.resources_B["retinographe"]
    fau_B = agent.resources_B["fauteuil"]

    # ── Assemblage KPI complet ────────────────────────────────────────────
    kpi = {
        "meta": {
            "source": "HDJ Agent — CHU Guyane",
            "specialite": "Endocrinologie-Diabétologie",
            "scenarios": "A (PMSI garde-fou) + B (réorganisation cible)",
            "avertissement": "données TYPE_SEJOUR=EXT — simulation hypothétique, pas une reclassification PMSI",
            "horizon_simulation_jours": DEFAULT_N_DAYS,
            "capacite_max_parallele": DEFAULT_MAX_PARALLEL,
        },
        "volume": {
            "total_sejours_analyses": agent.total,
            "hors_perimetre_endocrino": agent.kpis_A.not_applicable,
        },
        "scenario_A": {
            "label": "Garde-fou PMSI / réglementaire",
            "planifies": agent.kpis_A.scheduled,
            "deja_structures_hdj": agent.kpis_A.already_hdj,
            "convertibles_pmsi": agent.kpis_A.convertible,
            "requires_review": agent.kpis_A.requires_review,
            "candidats_validation_pmsi": agent.kpis_A.candidate_pmsi_validation,
            "uncertain": agent.kpis_A.uncertain,
            "non_planifies_horizon_plein": agent.kpis_A.not_scheduled,
            "delai_attente_moyen_j": round(agent.kpis_A.avg_wait_days, 1),
            "retinographe_occ_pct": round(ret_A.occupancy_rate(ts_A) * 100, 1),
            "retinographe_pic_utilisation": ret_A.peak_simultaneous(),
            "retinographe_capacite_totale": ret_A.total_units,
            "fauteuil_occ_pct": round(fau_A.occupancy_rate(ts_A) * 100, 1),
            "fauteuil_pic_utilisation": fau_A.peak_simultaneous(),
            "fauteuil_capacite_totale": fau_A.total_units,
        },
        "scenario_B": {
            "label": "Cible réorganisation HDJ",
            "simules": agent.kpis_B.scheduled,
            "dont_pmsi_validation_required": agent.kpis_B.pmsi_validation_required,
            "uncertain_non_simules": agent.kpis_B.requires_human_review,
            "low_candidate_non_simules": agent.kpis_B.low_candidate,
            "sans_creneau_horizon_plein": agent.kpis_B.not_scheduled,
            "gain_vs_A": agent.kpis_B.gain_vs_a,
            "delai_attente_moyen_j": round(agent.kpis_B.avg_wait_days, 1),
            "retinographe_occ_pct": round(ret_B.occupancy_rate(ts_B) * 100, 1),
            "retinographe_pic_utilisation": ret_B.peak_simultaneous(),
            "retinographe_capacite_totale": ret_B.total_units,
            "fauteuil_occ_pct": round(fau_B.occupancy_rate(ts_B) * 100, 1),
            "fauteuil_pic_utilisation": fau_B.peak_simultaneous(),
            "fauteuil_capacite_totale": fau_B.total_units,
            "repartition_pathways": dict(agent.kpis_B.by_pathway),
        },
        "patients_recurrents": ipp_metrics if ipp_metrics.get("has_ipp") else {"has_ipp": False},
        "limites_metier": [
            "Instruction Gradation DGOS/R1/DSS/1A/2020/52 non encodée → tous cas B = pmsi_validation_required",
            "Données TYPE_SEJOUR=EXT uniquement → simulation hypothétique",
            "Durées estimées (bilan=60min, rétino=90min, test_dyn=180min) → à valider équipe médicale",
            "Actes CCAM pompe/capteur/Holter absents → parcours initiation_dispositif non détectable",
            "Prototype aide à la décision — ne remplace pas une validation PMSI/DGOS",
        ],
    }

    # ── Exports ───────────────────────────────────────────────────────────

    # 1. kpi_summary.json
    p = out / "kpi_summary.json"
    p.write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {p}")

    # 2. kpi_summary.csv (format plat)
    rows = []
    rows.append({"categorie": "volume", "indicateur": "total_sejours_analyses",
                 "valeur": kpi["volume"]["total_sejours_analyses"], "unite": "séjours"})
    rows.append({"categorie": "volume", "indicateur": "hors_perimetre",
                 "valeur": kpi["volume"]["hors_perimetre_endocrino"], "unite": "séjours"})
    for sc_key, sc_label in (("scenario_A", "A"), ("scenario_B", "B")):
        d = kpi[sc_key]
        planif = d.get("planifies", d.get("simules", 0))
        for ind, val, unit in [
            ("planifies_simules",        planif,                    "séjours"),
            ("gain_vs_A",                d.get("gain_vs_A", 0),     "séjours"),
            ("retinographe_occ_pct",     d["retinographe_occ_pct"], "%"),
            ("fauteuil_occ_pct",         d["fauteuil_occ_pct"],     "%"),
            ("delai_attente_moyen_j",    d["delai_attente_moyen_j"],"jours"),
        ]:
            rows.append({"categorie": f"scenario_{sc_label}", "indicateur": ind,
                         "valeur": val, "unite": unit})
    if ipp_metrics.get("has_ipp"):
        for k, v in ipp_metrics.items():
            if k == "has_ipp":
                continue
            rows.append({"categorie": "patients_recurrents", "indicateur": k,
                         "valeur": v, "unite": ""})
    p = out / "kpi_summary.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    print(f"✓ {p}")

    # 3. scenario_comparison.json + .csv
    sc_comp = {
        "scenario":                   ["A — PMSI", "B — Réorganisation"],
        "planifies_simules":          [kpi["scenario_A"]["planifies"],
                                       kpi["scenario_B"]["simules"]],
        "gain_vs_A":                  [0, kpi["scenario_B"]["gain_vs_A"]],
        "retinographe_occ_pct":       [kpi["scenario_A"]["retinographe_occ_pct"],
                                       kpi["scenario_B"]["retinographe_occ_pct"]],
        "fauteuil_occ_pct":           [kpi["scenario_A"]["fauteuil_occ_pct"],
                                       kpi["scenario_B"]["fauteuil_occ_pct"]],
        "delai_attente_moyen_j":      [kpi["scenario_A"]["delai_attente_moyen_j"],
                                       kpi["scenario_B"]["delai_attente_moyen_j"]],
    }
    p = out / "scenario_comparison.json"
    p.write_text(json.dumps(sc_comp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {p}")
    p = out / "scenario_comparison.csv"
    pd.DataFrame(sc_comp).to_csv(p, index=False)
    print(f"✓ {p}")

    # 4. patients_recurrents_summary.csv
    if ipp_metrics.get("has_ipp"):
        prec = [{"indicateur": k, "valeur": v}
                for k, v in ipp_metrics.items() if k != "has_ipp"]
        p = out / "patients_recurrents_summary.csv"
        pd.DataFrame(prec).to_csv(p, index=False)
        print(f"✓ {p}")

    print(f"\n→ {len(list(out.iterdir()))} fichier(s) dans outputs/")
    print("→ Prêt pour import Lovable / dashboard jury\n")


if __name__ == "__main__":
    main()
