"""
HDJ Agent - Animation spatiale du parcours patient.

CLI : python demo_parcours_animation.py [--parcours-type {demo,retino,test_dyn,standard}]
API : from demo_parcours_animation import (
          generate_parcours_animation,
          infer_representative_parcours_from_active_data,
      )

Ameliorations v2 :
  - K adaptatif proportionnel a la distance visuelle (fin des teleportations)
  - Enregistrement de l'etat des soignants a chaque step (_InstrumentedModel)
  - Badge d'etat sur le patient (deplacement / attente / en soin / sorti)
  - Soignants : couleur differente selon engagement (disponible / avec patient)
  - Cercle d'occupation de la salle courante
  - Lignes d'engagement soignant <-> patient
  - Legende 8 entrees
  - Prints console compatibles Windows (ASCII pur)
"""
import os as _os
import numpy as np

from core.hopital.hopital_model import HopitalModel
from core.plan.plan_hopital import porte, POS, TYPE, dessiner_plan

# ---- Parcours disponibles -----------------------------------------------

PARCOURS_DEMO = [
    ("ACC",   "Accueil / enregistrement", 2),
    ("SOIN",  "Bilan infirmier",          3),
    ("BMED2", "Consultation medecin",     4),
    ("SCHIM", "Seance de chimio",         8),
    ("CH06",  "Surveillance",             5),
    ("SEC",   "Sortie / facturation",     2),
]

PARCOURS_RETINO = [
    ("ACC",   "Accueil / enregistrement", 2),
    ("SOIN",  "Bilan infirmier",          3),
    ("BMED2", "Depistage retinopathie",   4),
    ("SOIN",  "Resultat et conseil",      2),
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
    ("BMED2", "Consultation medecin",     4),
    ("SEC",   "Sortie / facturation",     2),
]

PARCOURS_BY_TYPE = {
    "demo":     PARCOURS_DEMO,
    "retino":   PARCOURS_RETINO,
    "test_dyn": PARCOURS_TEST_DYN,
    "standard": PARCOURS_STANDARD,
}

# ---- Detection CCAM / CIM-10 --------------------------------------------

_ACTES_RETINO   = {"BZQP001", "BZQK001", "BZQK002", "BZKB001"}
_ACTES_TEST_DYN = {"PZQP018", "JKQP002"}
_DIAGS_RETINO   = {"H36", "H35", "H34", "H33"}

# ---- Couleurs et labels d'etat ------------------------------------------

_COULEUR_ETAT = {
    "TRANSIT":      "#E55934",
    "ATTENTE_SOIN": "#F5A623",
    "SOIN":         "#2ECC71",
    "TERMINE":      "#95A5A6",
}
_ETAT_COURT = {
    "TRANSIT":      "deplacement",
    "ATTENTE_SOIN": "attente",
    "SOIN":         "en soin",
    "TERMINE":      "termine",
}
_ETAT_LONG = {
    "TRANSIT":      "se deplace",
    "ATTENTE_SOIN": "attend soignant",
    "SOIN":         "en soin",
    "TERMINE":      "sorti",
}

_COL_MED_LIBRE  = "#3498DB"   # bleu  - medecin disponible
_COL_MED_ACTIF  = "#E67E22"   # orange- medecin avec patient
_COL_PARA_LIBRE = "#8E44AD"   # violet- paramed disponible
_COL_PARA_ACTIF = "#C0392B"   # rouge - paramed avec patient

# Points de passage intermediaires pour les transitions couloir->couloir.
# Chaque paire de noeuds de transit adjacents qui forment un angle donne
# un ou deux points de "coin de couloir" pour eviter les diagonales visuelles.
# Geometrie derivee des BANDES du plan (plan_hopital.py).
#   CHM4 : bande horizontale y=40, x=[46,158]
#   CHM3 : bande horizontale y=66, x=[46,132]
#   CHM1 : bande horizontale y=66, x=[132,220]
#   CHM2 : bande horizontale y=40, x=[150,220]
#   CHM11: bande verticale   x=46, y=[42,66]  (connecteur CHM3/CHM4)
#   CHM5 : bande verticale   x=22, y=[56,88]
#   CHM6 : bande horizontale y=50, x=[22,46]
_TRANSIT_WAYPOINTS: dict = {
    # CHM3 (y=66) <-> CHM4 (y=40) : L-path via la jonction CHM11 en x=46
    ("CHM3",  "CHM4"):  [(46, 66), (46, 40)],
    ("CHM4",  "CHM3"):  [(46, 40), (46, 66)],
    # CHM5 (x=22) <-> CHM3 (y=66) : coin en haut-gauche du plan
    ("CHM5",  "CHM3"):  [(22, 66)],
    ("CHM3",  "CHM5"):  [(22, 66)],
    # CHM6 (y=50) <-> CHM11 (x=46) : coin gauche
    ("CHM6",  "CHM11"): [(46, 50)],
    ("CHM11", "CHM6"):  [(46, 50)],
    # CHM11 (x=46) <-> CHM3 (y=66) : haut de CHM11
    ("CHM11", "CHM3"):  [(46, 66)],
    ("CHM3",  "CHM11"): [(46, 66)],
    # CHM11 (x=46) <-> CHM4 (y=40) : bas de CHM11
    ("CHM11", "CHM4"):  [(46, 42)],
    ("CHM4",  "CHM11"): [(46, 42)],
    # CHM1 (y=66) <-> CHM2 (y=40) : coin droit via x~176
    ("CHM1",  "CHM2"):  [(176, 66), (176, 40)],
    ("CHM2",  "CHM1"):  [(176, 40), (176, 66)],
    # CHM1 <-> PATIO : descente depuis corridor haut
    ("CHM1",  "PATIO"): [(151, 66)],
    ("PATIO", "CHM1"):  [(151, 66)],
    # CHM2 <-> PATIO : montee depuis corridor bas
    ("CHM2",  "PATIO"): [(151, 40)],
    ("PATIO", "CHM2"):  [(151, 40)],
}


# ---- Modele instrumente --------------------------------------------------

class _InstrumentedModel(HopitalModel):
    """HopitalModel augmente : enregistre l'etat des soignants a chaque step."""

    def __init__(self, parcours, seed=42):
        super().__init__(parcours, seed)
        self.soignant_history: list = []

    def step(self) -> None:
        super().step()
        self.soignant_history.append([
            {
                "nom":           s.nom,
                "salle":         s.salle,
                "role":          s.role,
                "actif":         s.patient_actuel is not None,
                "type_soignant": s.type_soignant,
            }
            for s in self.soignants
        ])


# ---- Construction des frames --------------------------------------------

def _adaptive_k(pt_a, pt_b, px_per_frame: float = 4.5) -> int:
    """Nombre de frames d'interpolation proportionnel a la distance visuelle.

    Remplace le K=6 fixe : les longs segments de couloir (ex. CHM3->CHM1, 90 px)
    generent suffisamment de frames pour un mouvement fluide.
    """
    dist = float(np.linalg.norm(np.array(pt_b, float) - np.array(pt_a, float)))
    return max(5, int(dist / px_per_frame))


def _waypoints_between(node_a: str, node_b: str) -> list:
    """Waypoints visuels entre deux noeuds adjacents du graphe.

    Transit -> transit : on suit les coins de couloir declares dans
    _TRANSIT_WAYPOINTS pour eviter les diagonales visuelles.
    Sinon : centre -> porte_sortie -> porte_entree -> centre.
    """
    cur = np.array(POS[node_a], float)
    nxt = np.array(POS[node_b], float)

    if TYPE[node_a] == "transit" and TYPE[node_b] == "transit":
        junctions = _TRANSIT_WAYPOINTS.get((node_a, node_b))
        if junctions:
            return [cur] + [np.array(pt, float) for pt in junctions] + [nxt]
        return [cur, nxt]

    cdoor = porte(node_a) if TYPE[node_a] != "transit" else cur
    ndoor = porte(node_b) if TYPE[node_b] != "transit" else nxt
    way = [cur]
    if not np.allclose(cur, cdoor):
        way.append(cdoor)
    if not np.allclose(ndoor, nxt):
        way.append(ndoor)
    way.append(nxt)
    return way


def _build_rich_frames(model: "_InstrumentedModel") -> list:
    """Construit la sequence complete de frames depuis le modele instrumente.

    Chaque frame est un dict :
      px, py         - position visuelle du patient
      col            - couleur de l'etat patient
      etat           - cle d'etat Mesa (TRANSIT/ATTENTE_SOIN/SOIN/TERMINE)
      etat_court     - label court pour badge
      lib            - libelle de l'etape courante
      titre          - titre du cadre (heure + etat + etape)
      current_node   - noeud du graphe ou se trouve le patient
      soignants      - snapshot de l'etat des soignants
    """
    seq = [(h[1], h[2], h[3]) for h in model.historique]

    base_snap = [
        {
            "nom": s.nom, "salle": s.salle, "role": s.role,
            "actif": False, "type_soignant": s.type_soignant,
        }
        for s in model.soignants
    ]

    def get_snap(i: int) -> list:
        if model.soignant_history and i < len(model.soignant_history):
            return model.soignant_history[i]
        return base_snap

    frames: list = []

    for i, (node, etat, lib) in enumerate(seq):
        heure  = 8.0 + i * (10.0 / 60.0)
        snap   = get_snap(i)
        col    = _COULEUR_ETAT.get(etat, "#E55934")
        titre  = f"[{heure:.1f}h]  Patient : {_ETAT_LONG.get(etat, etat)}  |  {lib}"

        base = {
            "col":          col,
            "etat":         etat,
            "etat_court":   _ETAT_COURT.get(etat, etat),
            "lib":          lib,
            "titre":        titre,
            "current_node": node,
            "soignants":    snap,
        }

        if i + 1 < len(seq) and seq[i + 1][0] != node:
            # --- TRANSIT : interpolation avec K adaptatif par segment -------
            nxt_node = seq[i + 1][0]
            way = _waypoints_between(node, nxt_node)
            for j in range(len(way) - 1):
                K = _adaptive_k(way[j], way[j + 1])
                for k in range(K):
                    a = k / K
                    p = way[j] * (1.0 - a) + way[j + 1] * a
                    frames.append({**base, "px": float(p[0]), "py": float(p[1])})
        else:
            # --- STATIONNAIRE : 3 frames pour soin/attente, 1 sinon ---------
            n_frames = 3 if etat in ("ATTENTE_SOIN", "SOIN") else 1
            cur = np.array(POS[node], float)
            for _ in range(n_frames):
                frames.append({**base, "px": float(cur[0]), "py": float(cur[1])})

    return frames


# ---- API principale -----------------------------------------------------

def generate_parcours_animation(
    parcours=None,
    output_path: str = "outputs/plan_balade_soignants.gif",
) -> None:
    """Genere l'animation GIF du parcours patient.

    parcours    : liste de tuples (salle_id, libelle, duree_steps).
                  Si None, utilise PARCOURS_DEMO.
    output_path : chemin de sortie du GIF.
    """
    import matplotlib.pyplot as plt
    import matplotlib.animation as anim_mod
    import matplotlib.patches as mpatches
    import matplotlib.lines as mlines

    if parcours is None:
        parcours = PARCOURS_DEMO

    # Simulation instrumentee
    model = _InstrumentedModel(parcours, seed=42)
    while model.running and model.steps < 300:
        model.step()

    print(
        f"\nSimulation terminee en {model.steps} steps "
        f"({model.heure_actuelle:.1f}h), "
        f"{model.patient.nb_interactions} interaction(s) avec soignant."
    )

    frames = _build_rich_frames(model)
    print(f"Animation : {len(frames)} frames generees.")

    # ---- Fonction de dessin enrichi (closure sur plt/mpatches/mlines) ----

    def _draw_frame(ax, frame: dict) -> None:
        # Marqueurs soignants avec couleur d'etat dynamique
        dyn_markers = []
        for s in frame["soignants"]:
            sx, sy = POS[s["salle"]]
            if s["role"] == "Med":
                col_s = _COL_MED_ACTIF if s["actif"] else _COL_MED_LIBRE
            else:
                col_s = _COL_PARA_ACTIF if s["actif"] else _COL_PARA_LIBRE
            dyn_markers.append((sx, sy, col_s, s["nom"]))

        # Plan de base + marqueurs agents
        dessiner_plan(
            ax, model.G,
            patient_pos=(frame["px"], frame["py"], frame["col"]),
            soignant_markers=dyn_markers,
            titre=frame["titre"],
        )
        ax.title.set_fontsize(12)
        ax.title.set_fontweight("semibold")

        bx, by = frame["px"], frame["py"]

        # Badge d'etat sur le patient
        ax.text(
            bx, by + 6.5,
            frame["etat_court"],
            ha="center", va="bottom",
            fontsize=6.5, fontweight="bold", color="white",
            bbox=dict(
                boxstyle="round,pad=0.18",
                fc=frame["col"], ec="none", alpha=0.88,
            ),
            zorder=10,
        )

        # Cercle d'occupation de la salle courante (hors transit)
        cn = frame["current_node"]
        if (cn in POS
                and TYPE.get(cn, "transit") != "transit"
                and frame["etat"] != "TRANSIT"):
            cx, cy = POS[cn]
            ax.add_patch(
                mpatches.Circle(
                    (cx, cy), 7.5,
                    fill=False, ec=frame["col"],
                    lw=2.0, alpha=0.55, zorder=4,
                )
            )

        # Ligne d'engagement soignant <-> patient (tirete orange)
        for s in frame["soignants"]:
            if s["actif"]:
                sx, sy = POS[s["salle"]]
                ax.annotate(
                    "", xy=(bx, by), xytext=(sx, sy),
                    arrowprops=dict(
                        arrowstyle="-",
                        color="#F39C12",
                        lw=1.5, alpha=0.40,
                        linestyle=(0, (4, 3)),
                    ),
                    zorder=3,
                )

        # Legende
        legend_elts = [
            mpatches.Patch(fc=_COULEUR_ETAT["TRANSIT"],      label="Patient : deplacement"),
            mpatches.Patch(fc=_COULEUR_ETAT["ATTENTE_SOIN"], label="Patient : attente"),
            mpatches.Patch(fc=_COULEUR_ETAT["SOIN"],         label="Patient : en soin"),
            mpatches.Patch(fc=_COULEUR_ETAT["TERMINE"],      label="Patient : sorti"),
            mlines.Line2D([0], [0], marker="D", color="w",
                          markerfacecolor=_COL_MED_LIBRE,  markersize=8,
                          label="Medecin disponible"),
            mlines.Line2D([0], [0], marker="D", color="w",
                          markerfacecolor=_COL_MED_ACTIF,  markersize=8,
                          label="Medecin actif"),
            mlines.Line2D([0], [0], marker="D", color="w",
                          markerfacecolor=_COL_PARA_LIBRE, markersize=8,
                          label="IDE disponible"),
            mlines.Line2D([0], [0], marker="D", color="w",
                          markerfacecolor=_COL_PARA_ACTIF, markersize=8,
                          label="IDE actif"),
        ]
        ax.legend(
            handles=legend_elts,
            loc="lower left",
            fontsize=7, framealpha=0.9,
            ncol=2, borderpad=0.6,
            markerscale=1.4,
            edgecolor="#333",
            labelspacing=0.5,
            handlelength=1.8,
        )

    # ---- FuncAnimation ---------------------------------------------------

    fig, ax = plt.subplots(figsize=(14, 7.5))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.02)

    def draw(f_idx: int) -> None:
        _draw_frame(ax, frames[f_idx])

    ani = anim_mod.FuncAnimation(
        fig, draw, frames=len(frames), interval=100, repeat=True
    )
    plt.close(fig)

    out_dir = _os.path.dirname(output_path)
    if out_dir:
        _os.makedirs(out_dir, exist_ok=True)
    ani.save(output_path, writer=anim_mod.PillowWriter(fps=8))
    print(f"GIF sauvegarde : {output_path}")


# ---- Inference depuis les donnees actives --------------------------------

def infer_representative_parcours_from_active_data(df):
    """Construit un parcours representatif depuis les donnees actives de session.

    Retourne un dict :
        parcours       - liste de tuples (salle_id, libelle, duree_steps)
        parcours_type  - cle dans PARCOURS_BY_TYPE
        type           - label lisible
        raison         - explication du choix
        nb_sejours     - int ou None
    """
    if df is None or len(df) == 0:
        return {
            "parcours":      PARCOURS_DEMO,
            "parcours_type": "demo",
            "type":          "Parcours demo complet",
            "raison":        "Aucun fichier hospitalier actif - parcours exemple utilise.",
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
            "type":          "Parcours depistage retinopathie",
            "raison": (
                "Actes CCAM ou diagnostics ophtalmologiques compatibles "
                "avec depistage retinopathie detectes."
            ),
            "nb_sejours": nb_sejours,
        }

    if actes_detectes & _ACTES_TEST_DYN:
        return {
            "parcours":      PARCOURS_TEST_DYN,
            "parcours_type": "test_dyn",
            "type":          "Parcours test dynamique endocrinien",
            "raison": (
                "Actes PZQP018 ou test dynamique detectes - "
                "fauteuil medicalise requis."
            ),
            "nb_sejours": nb_sejours,
        }

    return {
        "parcours":      PARCOURS_STANDARD,
        "parcours_type": "standard",
        "type":          "Parcours bilan ambulatoire standard",
        "raison": (
            "Aucun acte ou diagnostic specifique detecte - "
            "parcours bilan ambulatoire standard applique."
        ),
        "nb_sejours": nb_sejours,
    }


# ---- CLI -----------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Genere l'animation du parcours patient HDJ."
    )
    parser.add_argument(
        "--parcours-type",
        default="demo",
        choices=list(PARCOURS_BY_TYPE.keys()),
        help="Type de parcours (demo | retino | test_dyn | standard).",
    )
    args = parser.parse_args()
    generate_parcours_animation(parcours=PARCOURS_BY_TYPE[args.parcours_type])
