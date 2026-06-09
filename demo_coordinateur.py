"""
Démo de l'Agent Coordinateur HDJ Endocrino — CHU Guyane.

Charge les données endocrino (2020-2023 et/ou 2024-2026), exécute le
coordinateur selon deux scénarios A (PMSI prudent) et B (réorganisation cible).

AVERTISSEMENT :
  Toutes les données sources sont TYPE_SEJOUR=EXT (consultations externes).
  Cette simulation représente une restructuration hypothétique — identifier
  quels séjours POURRAIENT être regroupés en HDJ — pas une reclassification
  PMSI réelle.

Usage :
    python demo_coordinateur.py
    python demo_coordinateur.py --annees 2024_2026
    python demo_coordinateur.py --annees toutes --days 10 --parallel 8
    python demo_coordinateur.py --detail           # détail planifiés scénario A
    python demo_coordinateur.py --detail --scenario B  # détail planifiés scénario B
"""

import argparse
import sys
from pathlib import Path
from typing import Set

import pandas as pd

# Ajout du répertoire du repo au path pour l'import des modules core
sys.path.insert(0, str(Path(__file__).parent))

from core.agents.coordinateur import CoordinateurAgent

# ── Chemins vers les fichiers de données ──────────────────────────────────
# Priorité : fichiers avec IPP si présents, sinon fallback vers les fichiers sans IPP.
_data_dir = Path("./data")
_all_ipp = list(_data_dir.glob("*IPP*.xlsx")) if _data_dir.exists() else []
_ipp_2020_2023 = next((f for f in _all_ipp if "2020_2023" in f.name), None)
_ipp_2024_2026 = next((f for f in _all_ipp if "2020_2023" not in f.name), None)

DATA_FILES = {
    "2020_2023": _ipp_2020_2023 or Path("./data/Données_Externes_Endocrino_et_diabéto_2020_2023_A.xlsx"),
    "2024_2026": _ipp_2024_2026 or Path("./data/Données_Externes_Endocrino_et_diabéto_A.xlsx"),
}
_IPP_ACTIVE = bool(_ipp_2020_2023 or _ipp_2024_2026)

# Priorité diagnostique endocrino : E2x/E34 > E1x > E03-E07 > E66 > E8x métabolique.
# Règle : si un séjour a plusieurs lignes avec codes différents, on garde le plus spécifique.
# Motivation : éviter qu'un acte de contexte (ex. E87) masque un diabète (E11) ou une
# pathologie endocrinienne rare (E27) qui justifie davantage un HDJ.
_DIAG_PRIORITY_PREFIXES = [
    ("E20", "E21", "E22", "E23", "E24", "E25", "E26", "E27", "E28", "E29", "E34"),  # troubles endocriniens spécifiques
    ("E10", "E11", "E13", "E14"),                                                    # diabète T1/T2
    ("E03", "E04", "E05", "E06", "E07"),                                             # thyroïde
    ("E66",),                                                                        # obésité
    ("E16", "E46", "E61", "E64", "E74", "E75", "E83", "E87", "E88"),                # métabolique
]


def _diag_priority(code: str) -> int:
    """Retourne l'indice de priorité (plus bas = plus prioritaire). 999 si non reconnu."""
    if not isinstance(code, str):
        return 999
    c = code.upper().strip()
    for rank, prefixes in enumerate(_DIAG_PRIORITY_PREFIXES):
        if any(c.startswith(p) for p in prefixes):
            return rank
    return 999


def aggregate_by_sejour(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrège les lignes par NUM SEJOUR.

    Structure source : 1 ligne = 1 combinaison (acte CCAM × cotation NGAP), pas 1 séjour.
    → N lignes par séjour quand il y a plusieurs actes ou cotations.

    Règles d'agrégation :
      - CODE DIAG       : diagnostic endocrino/métabolique le plus spécifique
                          (priorité E2x/E34 > E1x > E03-07 > E66 > E8x métabolique)
      - LISTE ACTES CCAM MVT : union de tous les actes CCAM du séjour
                               (CODE ACTE + LISTE ACTES CCAM MVT de chaque ligne)
      - Autres colonnes : première valeur non-nulle (first)
    """
    n_lignes = len(df)

    def _best_diag(codes: pd.Series) -> str:
        valid = [c for c in codes.dropna() if str(c).strip() not in ("", "nan", "NAN")]
        if not valid:
            return ""
        return min(valid, key=_diag_priority)

    def _union_actes(group: pd.DataFrame) -> str:
        actes: Set[str] = set()
        for val in group["CODE ACTE"].dropna():
            s = str(val).strip().upper()
            if s and s not in ("NAN", "NONE"):
                actes.add(s)
        for val in group["LISTE ACTES CCAM MVT"].dropna():
            for a in str(val).upper().split(","):
                a = a.strip()
                if a and a not in ("NAN", "NONE"):
                    actes.add(a)
        return ",".join(sorted(actes))

    rows = []
    for sejour_id, grp in df.groupby("NUM SEJOUR", sort=False):
        # Première ligne comme base (first non-null pour champs scalaires)
        base = grp.ffill().iloc[0].to_dict()
        base["CODE DIAG"] = _best_diag(grp["CODE DIAG"])
        base["LISTE ACTES CCAM MVT"] = _union_actes(grp)
        # CODE ACTE : vide après union (tous les actes sont déjà dans LISTE ACTES CCAM MVT)
        base["CODE ACTE"] = ""
        rows.append(base)

    aggregated = pd.DataFrame(rows)
    n_sejours = len(aggregated)
    print(f"[INFO] Agrégation : {n_lignes} lignes initiales → {n_sejours} séjours uniques\n")
    return aggregated


def compute_ipp_metrics(df_raw: pd.DataFrame) -> dict:
    """Calcule les métriques de récurrence patient (IPP). Retourne {} si colonne absente."""
    IPP_COL = "NUM IPP PATIENT"
    if IPP_COL not in df_raw.columns:
        return {}
    ipp = df_raw[IPP_COL].dropna()
    if ipp.empty:
        return {}
    ipp_counts = ipp.value_counts()
    recurrents = int((ipp_counts > 1).sum())
    n_uniques = int(ipp.nunique())
    rec_ipps = ipp_counts[ipp_counts > 1].index
    return {
        "has_ipp": True,
        "total_lignes": len(df_raw),
        "ipp_uniques": n_uniques,
        "patients_recurrents": recurrents,
        "pct_recurrents": round(recurrents / n_uniques * 100, 1) if n_uniques else 0.0,
        "venues_moy": round(float(ipp_counts.mean()), 2),
        "venues_max": int(ipp_counts.max()),
        "lignes_patients_recurrents": int(df_raw[IPP_COL].isin(rec_ipps).sum()),
    }


def print_ipp_section(metrics: dict) -> None:
    """Affiche la section récurrence IPP dans le dashboard (agrégats uniquement)."""
    sep = "═" * 68
    print(f"\n{sep}")
    print("  ANALYSE RÉCURRENCE PATIENTS (IPP)")
    print("  Fragmentation du parcours & potentiel de regroupement HDJ")
    print(sep)
    print(f"  {'Patients uniques (IPP)':<50} {metrics['ipp_uniques']:>5}")
    print(f"  {'Patients récurrents (> 1 venue)':<50} {metrics['patients_recurrents']:>5}")
    print(f"  {'% patients récurrents':<50} {metrics['pct_recurrents']:>4.1f}%")
    print(f"  {'Venues moyennes / patient':<50} {metrics['venues_moy']:>5.2f}")
    print(f"  {'Maximum de venues pour un même patient':<50} {metrics['venues_max']:>5}")
    print(f"  {'Lignes issues de patients récurrents':<50} {metrics['lignes_patients_recurrents']:>5}")
    print()
    print("  → Les retours multiples d'un même patient (fragmentation du parcours)")
    print("    révèlent un potentiel de regroupement en HDJ : moins de déplacements,")
    print("    meilleure coordination soignants, tarification GHS journalier optimisée.")
    print(f"\n{sep}\n")


def load_data(annees: str) -> pd.DataFrame:
    files = DATA_FILES if annees == "toutes" else {annees: DATA_FILES[annees]}
    dfs = []
    for label, path in files.items():
        if not path.exists():
            print(f"[WARN] Fichier introuvable : {path}")
            continue
        df = pd.read_excel(path, engine="openpyxl")
        df["_source"] = label
        dfs.append(df)
        ipp_tag = " avec IPP" if "IPP" in path.name else " (sans IPP)"
        print(f"[INFO] Chargé {label}{ipp_tag} : {len(df)} lignes")
    if not dfs:
        raise FileNotFoundError(
            "Aucun fichier de données trouvé dans ~/claude_context_Hackathon_SMA/"
        )
    combined = pd.concat(dfs, ignore_index=True)
    print(f"[INFO] Total combiné : {len(combined)} lignes brutes")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Démo Agent Coordinateur HDJ Endocrino"
    )
    parser.add_argument(
        "--annees",
        default="toutes",
        choices=["toutes", "2020_2023", "2024_2026"],
        help="Jeu de données (défaut: toutes)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Horizon de simulation en jours ouvrés (défaut: 5)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=6,
        help="Places HDJ simultanées dans l'unité (défaut: 6, hypothèse)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Affiche le détail complet des séjours planifiés",
    )
    parser.add_argument(
        "--scenario",
        default="A",
        choices=["A", "B"],
        help="Scénario pour --detail : A (PMSI prudent) ou B (réorganisation cible)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 62)
    print("  HDJ Agent — Démo Coordinateur Ordonnanceur")
    print(f"  Horizon : {args.days} jours | Capacité : {args.parallel} places/créneau")
    print("=" * 62)
    print(
        "\n  AVERTISSEMENT : données TYPE_SEJOUR=EXT uniquement.\n"
        "  Simulation de restructuration hypothétique en HDJ,\n"
        "  pas une reclassification PMSI réelle.\n"
    )

    df_raw = load_data(args.annees)
    ipp_metrics = compute_ipp_metrics(df_raw)
    if ipp_metrics.get("has_ipp"):
        n_ipp_files = sum(1 for f in [_ipp_2020_2023, _ipp_2024_2026] if f is not None)
        print(f"[INFO] Fichiers IPP actifs ({n_ipp_files}/2) — {ipp_metrics['ipp_uniques']} patients uniques détectés\n")
    df = aggregate_by_sejour(df_raw)

    agent = CoordinateurAgent(n_days=args.days, max_parallel=args.parallel)
    agent.load_data(df)
    agent.run()
    agent.print_dashboard()

    if ipp_metrics.get("has_ipp"):
        print_ipp_section(ipp_metrics)

    if args.detail:
        agent.print_scheduled_full_detail(scenario=args.scenario)


if __name__ == "__main__":
    main()
