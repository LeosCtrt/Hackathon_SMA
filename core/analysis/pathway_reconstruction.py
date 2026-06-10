"""
Reconstruction des parcours fragmentés à partir des IPP.

Objectif : identifier les patients qui reviennent plusieurs fois
en consultation externe et dont les venues pourraient être regroupées
en Hôpital de Jour (HDJ).

Ne jamais exporter d'IPP brut. Tous les outputs sont des agrégats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def _classify_fragmentation(n_venues: int) -> str:
    if n_venues == 1:
        return "pas_de_fragmentation"
    if n_venues <= 3:
        return "fragmentation_faible"
    if n_venues <= 9:
        return "fragmentation_moderee"
    if n_venues <= 20:
        return "fragmentation_forte"
    return "hyper_recurrence"


def _fragmentation_interpretation(level: str) -> str:
    return {
        "pas_de_fragmentation": "Venue unique — pas de signal de fragmentation.",
        "fragmentation_faible": "2–3 venues — fragmentation légère, potentiel de regroupement à évaluer.",
        "fragmentation_moderee": "4–9 venues — fragmentation notable, regroupement en HDJ recommandé.",
        "fragmentation_forte": "10–20 venues — fragmentation forte, création ou extension HDJ justifiée.",
        "hyper_recurrence": "Plus de 20 venues — hyper-récurrence, prise en charge structurée urgente.",
    }.get(level, "")


def reconstruct_patient_pathways(
    df: pd.DataFrame,
    output_dir: str | Path = "outputs",
) -> Dict[str, Any]:
    """
    Reconstruit les parcours patients à partir des IPP.

    Args:
        df         : DataFrame chargé par hospital_data_loader.
        output_dir : dossier de sortie pour les fichiers JSON.

    Returns:
        dict contenant pathway_summary et fragmentation_segments.
    """
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    IPP_COL = "NUM IPP PATIENT"
    has_ipp = IPP_COL in df.columns

    if not has_ipp or df[IPP_COL].dropna().empty:
        empty = {
            "error": "Colonne IPP absente ou vide — reconstruction impossible",
            "recommendation": "Utiliser les fichiers avec IPP pour activer cette analyse.",
        }
        (out / "pathway_reconstruction.json").write_text(
            json.dumps(empty, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out / "fragmentation_segments.json").write_text(
            json.dumps(empty, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"pathway_reconstruction": empty, "fragmentation_segments": empty}

    ipp_counts = df[IPP_COL].dropna().value_counts()
    n_total = int(ipp_counts.count())
    n_recurrent = int((ipp_counts > 1).sum())
    n_single = n_total - n_recurrent

    # Distribution par tranches
    distribution = {
        "1_venue": int((ipp_counts == 1).sum()),
        "2_3_venues": int(((ipp_counts >= 2) & (ipp_counts <= 3)).sum()),
        "4_9_venues": int(((ipp_counts >= 4) & (ipp_counts <= 9)).sum()),
        "10_20_venues": int(((ipp_counts >= 10) & (ipp_counts <= 20)).sum()),
        "plus_20_venues": int((ipp_counts > 20).sum()),
    }

    # Lignes associées aux récurrents
    rec_ipps = ipp_counts[ipp_counts > 1].index
    lines_recurrent = int(df[IPP_COL].isin(rec_ipps).sum())

    # Actes et diagnostics dominants chez les récurrents
    df_rec = df[df[IPP_COL].isin(rec_ipps)]
    top_diags: Dict[str, int] = {}
    if "CODE DIAG" in df.columns:
        top_diags = (
            df_rec["CODE DIAG"].dropna().value_counts().head(10).to_dict()
        )

    top_ccam: Dict[str, int] = {}
    if "LISTE ACTES CCAM MVT" in df.columns:
        top_ccam = (
            df_rec["LISTE ACTES CCAM MVT"].dropna().value_counts().head(5).to_dict()
        )

    # Score de potentiel de regroupement
    pct_rec = round(n_recurrent / n_total * 100, 1) if n_total else 0.0
    grouping_potential = (
        "fort" if pct_rec >= 40 else
        "modere" if pct_rec >= 20 else
        "faible"
    )

    # ── Segments de fragmentation ─────────────────────────────────────────
    segments: List[Dict[str, Any]] = []
    for tranche, count in distribution.items():
        if count == 0:
            continue
        n_venues_label = tranche.replace("_", " ").replace("venues", "venue(s)")
        level_map = {
            "1_venue": "pas_de_fragmentation",
            "2_3_venues": "fragmentation_faible",
            "4_9_venues": "fragmentation_moderee",
            "10_20_venues": "fragmentation_forte",
            "plus_20_venues": "hyper_recurrence",
        }
        level = level_map[tranche]
        lines_in_segment = int(
            df[df[IPP_COL].isin(
                ipp_counts[
                    (ipp_counts >= (1 if tranche == "1_venue" else
                                    2 if tranche == "2_3_venues" else
                                    4 if tranche == "4_9_venues" else
                                    10 if tranche == "10_20_venues" else 21))
                    & (ipp_counts <= (1 if tranche == "1_venue" else
                                     3 if tranche == "2_3_venues" else
                                     9 if tranche == "4_9_venues" else
                                     20 if tranche == "10_20_venues" else 9999))
                ].index
            )][IPP_COL].count()
        )
        segments.append({
            "tranche": tranche,
            "label": n_venues_label,
            "n_patients": count,
            "lignes_associees": lines_in_segment,
            "niveau_fragmentation": level,
            "interpretation": _fragmentation_interpretation(level),
            "action_recommandee": (
                "Analyse au cas par cas" if level == "pas_de_fragmentation" else
                "Évaluation éligibilité HDJ" if level == "fragmentation_faible" else
                "Regroupement HDJ recommandé" if level == "fragmentation_moderee" else
                "Création / renforcement HDJ justifié" if level == "fragmentation_forte" else
                "Prise en charge structurée prioritaire"
            ),
        })

    pathway_summary: Dict[str, Any] = {
        "analyse": "Reconstruction des parcours fragmentés — données réelles",
        "note": "Aucun IPP individuel n'est exposé dans ce rapport.",
        "totaux": {
            "ipp_uniques": n_total,
            "patients_non_recurrents": n_single,
            "patients_recurrents": n_recurrent,
            "pct_recurrents": pct_rec,
            "venues_max": int(ipp_counts.max()),
            "venues_moy": round(float(ipp_counts.mean()), 2),
            "lignes_patients_recurrents": lines_recurrent,
            "pct_lignes_recurrents": round(lines_recurrent / len(df) * 100, 1),
        },
        "distribution_venues": distribution,
        "potentiel_regroupement_hdj": grouping_potential,
        "top_diagnostics_recurrents": top_diags,
        "top_actes_ccam_recurrents": top_ccam,
        "interpretation_globale": (
            f"{pct_rec:.1f}% des patients ont plusieurs venues sur la période analysée. "
            "Ce signal de fragmentation représente un potentiel de structuration en HDJ "
            "pour réduire les passages multiples, améliorer la coordination soignants "
            "et instruire le potentiel de valorisation avec le DIM/PMSI."
        ),
    }

    fragmentation_summary: Dict[str, Any] = {
        "segments": segments,
        "synthese": {
            "patients_total": n_total,
            "patients_fragmentes": n_recurrent,
            "potentiel_regroupement": grouping_potential,
        },
        "note": "Classification basée sur le nombre de venues par IPP anonymisé.",
    }

    (out / "pathway_reconstruction.json").write_text(
        json.dumps(pathway_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "fragmentation_segments.json").write_text(
        json.dumps(fragmentation_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "pathway_reconstruction": pathway_summary,
        "fragmentation_segments": fragmentation_summary,
    }
