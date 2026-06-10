"""
HDJ Agent — Animation spatiale du parcours patient.

CLI : python demo_parcours_animation.py [--parcours-type {demo,retino,test_dyn,standard}]
API : from demo_parcours_animation import (
          generate_parcours_animation,
          infer_representative_parcours_from_active_data,
      )
"""
import os as _os
import numpy as np

from core.hopital.hopital_model import HopitalModel
from core.plan.plan_hopital import porte, POS, TYPE, dessiner_plan

# ── Parcours disponibles ───────────────────────────────────────────────────

PARCOURS_DEMO = [
    ("ACC",   "Accueil / enregistrement", 2),
    ("SOIN",  "Bilan infirmier",          3),
    ("BMED2", "Consultation médecin",     4),
    ("SCHIM", "Séance de chimio",         8),
    ("CH06",  "Surveillance",             5),
    ("SEC",   "Sortie / facturation",     2),
]

PARCOURS_RETINO = [
    ("ACC",   "Accueil / enregistrement", 2),
    ("SOIN",  "Bilan infirmier",          3),
    ("BMED2", "Dépistage rétinopathie",   4),
    ("SOIN",  "Résultat et conseil",      2),
    ("SEC",   "Sortie / facturation",     2),
]

PARCOURS_TEST_DYN = [
    ("ACC",   "Accueil / enregistrement",   2),
    ("SOIN",  "Bilan infirmier",            3),
    ("BMED2", "Consultation endocrinienne", 4),
    ("SCHIM", "Test dynamique / fauteuil",  8),
    ("CH06",  "Surveillance post-test",     5),
    ("SEC",   "Sortie / facturation",       2),
]

PARCOURS_STANDARD = [
    ("ACC",   "Accueil / enregistrement", 2),
    ("SOIN",  "Bilan infirmier",          3),
    ("BMED2", "Consultation médecin",     4),
    ("SEC",   "Sortie / facturation",     2),
]

PARCOURS_BY_TYPE = {
    "demo":     PARCOURS_DEMO,
    "retino":   PARCOURS_RETINO,
    "test_dyn": PARCOURS_TEST_DYN,
    "standard": PARCOURS_STANDARD,
}

# ── Règles de détection CCAM / CIM-10 ─────────────────────────────────────

_ACTES_RETINO   = {"BZQP001", "BZQK001", "BZQK002", "BZKB001"}
_ACTES_TEST_DYN = {"PZQP018", "JKQP002"}
_DIAGS_RETINO   = {"H36", "H35", "H34", "H33"}


# ── API ────────────────────────────────────────────────────────────────────

def infer_representative_parcours_from_active_data(df):
    """Construit un parcours représentatif depuis les données actives de session.

    Retourne un dict :
        parcours       — liste de tuples (salle_id, libelle, duree_steps)
        parcours_type  — clé dans PARCOURS_BY_TYPE
        type           — label lisible
        raison         — explication du choix
        nb_sejours     — int ou None
    """
    if df is None or len(df) == 0:
        return {
            "parcours":      PARCOURS_DEMO,
            "parcours_type": "demo",
            "type":          "Parcours démo complet",
            "raison":        "Aucun fichier hospitalier actif — parcours exemple utilisé.",
            "nb_sejours":    None,
        }

    nb_sejours = len(df)
    df_u = df.copy()
    df_u.columns = df_u.columns.str.strip().str.upper()

    actes_detectes: set = set()
    if "LISTE ACTES CCAM MVT" in df_u.columns:
        for val in df_u["LISTE ACTES CCAM MVT"].dropna():
            for code in str(val).split(";"):
                actes_detectes.add(code.strip().upper()[:8])

    diags_detectes: set = set()
    if "CODE DIAG" in df_u.columns:
        diags_detectes = set(df_u["CODE DIAG"].dropna().str.upper().str[:3])

    if actes_detectes & _ACTES_RETINO or diags_detectes & _DIAGS_RETINO:
        return {
            "parcours":      PARCOURS_RETINO,
            "parcours_type": "retino",
            "type":          "Parcours dépistage rétinopathie",
            "raison": (
                "Actes CCAM ou diagnostics ophtalmologiques compatibles "
                "avec dépistage rétinopathie détectés."
            ),
            "nb_sejours": nb_sejours,
        }

    if actes_detectes & _ACTES_TEST_DYN:
        return {
            "parcours":      PARCOURS_TEST_DYN,
            "parcours_type": "test_dyn",
            "type":          "Parcours test dynamique endocrinien",
            "raison": (
                "Actes PZQP018 ou test dynamique détectés — "
                "fauteuil médicalisé requis."
            ),
            "nb_sejours": nb_sejours,
        }

    return {
        "parcours":      PARCOURS_STANDARD,
        "parcours_type": "standard",
        "type":          "Parcours bilan ambulatoire standard",
        "raison": (
            "Aucun acte ou diagnostic spécifique détecté — "
            "parcours bilan ambulatoire standard appliqué."
        ),
        "nb_sejours": nb_sejours,
    }


def generate_parcours_animation(
    parcours=None,
    output_path="outputs/plan_balade_soignants.gif",
):
    """Génère l'animation GIF du parcours patient.

    parcours    : liste de tuples (salle_id, libelle, duree_steps).
                  Si None, utilise PARCOURS_DEMO.
    output_path : chemin de sortie du GIF.
    """
    import matplotlib.pyplot as plt
    import matplotlib.animation as anim_mod

    if parcours is None:
        parcours = PARCOURS_DEMO

    model = HopitalModel(parcours, seed=42)
    while model.running and model.steps < 300:
        model.step()

    print(
        f"\nSimulation terminée en {model.steps} steps "
        f"({model.heure_actuelle:.1f}h), "
        f"{model.patient.nb_interactions} interaction(s) avec soignant."
    )

    seq = [(h[1], h[2], h[3]) for h in model.historique]

    COULEUR_ETAT = {
        "TRANSIT":      "#E24B4A",
        "ATTENTE_SOIN": "#F5A623",
        "SOIN":         "#1D9E75",
        "TERMINE":      "#888888",
    }

    K = 6
    frames = []
    for i in range(len(seq)):
        node, etat, lib = seq[i]
        cur   = np.array(POS[node], float)
        cdoor = porte(node) if TYPE[node] != "transit" else cur
        col   = COULEUR_ETAT.get(etat, "#E24B4A")

        if i + 1 < len(seq) and seq[i + 1][0] != node:
            nxt   = seq[i + 1][0]
            npt   = np.array(POS[nxt], float)
            ndoor = porte(nxt) if TYPE[nxt] != "transit" else npt
            way = [cur]
            if not np.allclose(cur, cdoor):
                way.append(cdoor)
            if not np.allclose(ndoor, npt):
                way.append(ndoor)
            way.append(npt)
            for j in range(len(way) - 1):
                for k in range(K):
                    a = k / K
                    p = way[j] * (1 - a) + way[j + 1] * a
                    frames.append((p[0], p[1], "#E24B4A", lib, "TRANSIT"))
        else:
            frames.append((cur[0], cur[1], col, lib, etat))

    soignant_markers = []
    for s in model.soignants:
        x, y = POS[s.salle]
        col  = "#4A90D9" if s.role == "Med" else "#9B59B6"
        soignant_markers.append((x, y, col, s.nom))

    fig, ax = plt.subplots(figsize=(13, 7))
    etxt = {
        "TRANSIT":      "se déplace",
        "ATTENTE_SOIN": "en attente soignant",
        "SOIN":         "en soin",
        "TERMINE":      "sorti",
    }

    def draw(f):
        x, y, col, lib, etat = frames[f]
        dessiner_plan(
            ax, model.G,
            patient_pos=(x, y, col),
            soignant_markers=soignant_markers,
            titre=f"{etxt.get(etat, etat)} — {lib}",
        )

    ani = anim_mod.FuncAnimation(fig, draw, frames=len(frames), interval=160, repeat=True)
    plt.close(fig)

    out_dir = _os.path.dirname(output_path)
    if out_dir:
        _os.makedirs(out_dir, exist_ok=True)
    ani.save(output_path, writer=anim_mod.PillowWriter(fps=7))


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Génère l'animation du parcours patient HDJ."
    )
    parser.add_argument(
        "--parcours-type",
        default="demo",
        choices=list(PARCOURS_BY_TYPE.keys()),
        help="Type de parcours à simuler (demo | retino | test_dyn | standard).",
    )
    args = parser.parse_args()
    generate_parcours_animation(parcours=PARCOURS_BY_TYPE[args.parcours_type])
