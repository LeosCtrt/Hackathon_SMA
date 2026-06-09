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

# ── Chemins vers les fichiers de données (hors repo) ───────────────────────
DATA_FILES = {
    "2020_2023": Path.home() / "claude_context_Hackathon_SMA/donnees_endocrino_2020_2023.xlsx",
    "2024_2026": Path.home() / "claude_context_Hackathon_SMA/Données_Externes_Endocrino_et_diabéto.xlsx",
}

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
        print(f"[INFO] Chargé {label} : {len(df)} lignes")
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

    df = load_data(args.annees)
    df = aggregate_by_sejour(df)

    agent = CoordinateurAgent(n_days=args.days, max_parallel=args.parallel)
    agent.load_data(df)
    agent.run()
    agent.print_dashboard()

    if args.detail:
        agent.print_scheduled_full_detail(scenario=args.scenario)


if __name__ == "__main__":
    main()
