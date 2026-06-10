"""
Estimation médico-économique HDJ — 3 niveaux de scénario.

Toutes les estimations financières sont paramétrables et doivent
être validées avec le DIM/PMSI avant toute utilisation opérationnelle.

Positionnement : estimation opérationnelle d'aide à la décision,
pas une projection de recettes certifiée.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml


def _load_yaml_params() -> Dict[str, Any]:
    yaml_path = Path("core/config/hdj_metier.yaml")
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    actes = cfg["actes_et_taches"]["actes_ccam_hdj_endocrino"]
    return {
        "duree_retinographie_min": int(actes["retinographie"]["duree_min"]),
        "duree_bilan_diabete_min": int(actes["bilan_annuel_diabete"]["duree_min"]),
        "duree_test_dynamique_min": int(actes["test_dynamique_endocrinien"]["duree_min"]),
        "duree_consultation_min": int(actes["consultation_simple"]["duree_min"]),
        "fauteuil_quantite": int(
            cfg["ressources_hdj"]["mvp_ressources_goulot"]["fauteuil_medicalise"]["quantite"]
        ),
        "retinographe_quantite": int(
            cfg["ressources_hdj"]["mvp_ressources_goulot"]["retinographe"]["quantite"]
        ),
        "slots_par_jour": int(
            cfg["contraintes_systeme"]["horaires_simulation"]["slots_par_jour"]
        ),
    }


def build_medico_economic_estimates(
    kpis_A: Dict[str, Any],
    kpis_B: Dict[str, Any],
    ipp_metrics: Dict[str, Any] | None = None,
    forfait_hdj_ref: float = 600.0,
    output_path: str | Path = "outputs/medico_economic_estimates.json",
) -> Dict[str, Any]:
    """
    Produit une estimation médico-économique prudente à 3 niveaux.

    Args:
        kpis_A         : dict KPIs Scénario A (clés : planifies, …)
        kpis_B         : dict KPIs Scénario B (clés : simules, gain_vs_A, …)
        ipp_metrics    : métriques IPP pour le niveau transformation.
        forfait_hdj_ref: forfait journalier HDJ de référence (€) — à valider DIM.
        output_path    : chemin de sortie JSON.

    Returns:
        dict medico_economic_estimates.
    """
    params = _load_yaml_params()

    vol_A = kpis_A.get("planifies", 0)
    vol_B = kpis_B.get("simules", 0)
    gain_B = kpis_B.get("gain_vs_A", 0)
    rec_patients = ipp_metrics.get("patients_recurrents", 0) if ipp_metrics else 0
    lignes_rec = ipp_metrics.get("lignes_patients_recurrents", 0) if ipp_metrics else 0

    note_estimation = (
        "Estimation opérationnelle basée sur le forfait journalier HDJ de référence "
        f"({forfait_hdj_ref}€/journée). "
        "À valider avec le DIM/PMSI avant toute projection financière officielle."
    )

    niveaux = [
        {
            "niveau": "prudent",
            "label": "Niveau 1 — Prudent (PMSI garde-fou)",
            "description": (
                "Seulement les séjours avec référence PMSI solide (scénario A). "
                "Approche conservatrice, risque réglementaire minimal."
            ),
            "volume_concerne": vol_A,
            "hypothese": f"Forfait journalier HDJ = {forfait_hdj_ref}€ (à valider DIM)",
            "valeur_organisationnelle": (
                f"{vol_A} journées HDJ structurées vs consultations fragmentées"
            ),
            "potentiel_valorisation_a_valider": round(vol_A * forfait_hdj_ref, 0),
            "unite": "€/période analysée",
            "validation_requise": "DIM + Chef de service",
            "decision_possible": "Ouverture ou consolidation HDJ existant",
            "non_financial_value": [
                "Réduction des passages multiples pour les cas déjà HDJ",
                "Meilleure traçabilité PMSI des journées HDJ",
                "Facturation sécurisée",
            ],
        },
        {
            "niveau": "operationnel",
            "label": "Niveau 2 — Opérationnel (réorganisation après validation)",
            "description": (
                "Après validation DIM/PMSI du scénario B. "
                "Inclut les candidats organisationnels non encore codés en HDJ."
            ),
            "volume_concerne": vol_B,
            "gain_vs_prudent": gain_B,
            "hypothese": f"Forfait journalier HDJ = {forfait_hdj_ref}€ (à valider DIM)",
            "valeur_organisationnelle": (
                f"+{gain_B} séjours supplémentaires structurables en HDJ après validation"
            ),
            "potentiel_valorisation_a_valider": round(vol_B * forfait_hdj_ref, 0),
            "unite": "€/période analysée",
            "validation_requise": (
                "DIM + Chef de service + Direction des opérations + "
                "Instruction Gradation DGOS/R1/DSS/1A/2020/52"
            ),
            "decision_possible": "Extension HDJ + nouveaux parcours",
            "non_financial_value": [
                "Réduction de la fragmentation des parcours",
                "Meilleure coordination soignants",
                "Libération de créneaux de consultation",
                "Amélioration expérience patient",
            ],
        },
        {
            "niveau": "transformation",
            "label": "Niveau 3 — Transformation (création pathways HDJ prioritaires)",
            "description": (
                "Inclut le regroupement des patients récurrents et la création "
                "de nouveaux parcours HDJ dédiés. Horizon 12–24 mois."
            ),
            "volume_concerne": rec_patients,
            "lignes_fragmentees": lignes_rec,
            "hypothese": (
                f"Potentiel de regroupement estimé sur {rec_patients} patients récurrents. "
                f"Forfait journalier HDJ = {forfait_hdj_ref}€ (à valider DIM)."
            ),
            "valeur_organisationnelle": (
                f"Réduction de {lignes_rec} passages fragmentés pour {rec_patients} patients"
            ),
            "potentiel_valorisation_a_valider": "À calculer avec DIM après définition des protocoles HDJ",
            "unite": "Non chiffrable sans protocoles définis",
            "validation_requise": (
                "DIM + Chef de service + Cadre HDJ + Direction des opérations + DSI"
            ),
            "decision_possible": "Plan de transformation ambulatoire à 18 mois",
            "non_financial_value": [
                f"Jusqu'à {lignes_rec} passages évités si tous regroupés",
                "Amélioration significative expérience patient chronique",
                "Réduction charge administrative (admissions multiples)",
                "Données pour benchmarking inter-CHU",
                "Base pour certification HAS parcours coordonnés",
            ],
        },
    ]

    estimates: Dict[str, Any] = {
        "analyse": "Estimation médico-économique HDJ — CHU Guyane Endocrino-Diabétologie",
        "avertissement": (
            "Ces estimations sont à valider avec le DIM/PMSI avant toute utilisation "
            "financière officielle. Il ne s'agit pas d'une projection de recettes certifiée."
        ),
        "parametres": {
            "forfait_hdj_reference_euros": forfait_hdj_ref,
            "source_forfait": "Paramètre de référence — à adapter au GHS réel CHU Guyane",
            "durees_yaml": params,
        },
        "niveaux": niveaux,
        "synthese": {
            "volume_total_analyse": kpis_A.get("total", 0),
            "vol_prudent": vol_A,
            "vol_operationnel": vol_B,
            "patients_recurrents_impactes": rec_patients,
        },
        "valeur_non_financiere": {
            "moins_de_deplacements": f"{rec_patients} patients récurrents, {lignes_rec} lignes fragmentées",
            "meilleure_coordination": "Regroupement actes → moins d'intervenants séparés",
            "anticipation_ressources": "Planification déterministe vs flux imprévu",
            "aide_priorisation_gouvernance": "Dashboard décisionnel avec données réelles",
        },
        "note_estimation": note_estimation,
    }

    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(estimates, ensure_ascii=False, indent=2), encoding="utf-8")

    return estimates
