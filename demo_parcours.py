import numpy as np
from IPython.display import HTML
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from core.hopital.hopital_model import HopitalModel
from core.plan.plan_hopital import porte, POS, TYPE, dessiner_plan

PARCOURS = [
    ("ACC",   "Accueil / enregistrement", 2),
    ("SOIN",  "Bilan infirmier",          3),
    ("BMED2", "Consultation medecin",     4),
    ("SCHIM", "Seance de chimio",         8),
    ("CH06",  "Surveillance",             5),
    ("SEC",   "Sortie / facturation",     2),
]
 
model = HopitalModel(PARCOURS, seed=42)
while model.running and model.steps < 300:
    model.step()
 
print(f"\nSimulation terminee en {model.steps} steps "
      f"({model.heure_actuelle:.1f}h), "
      f"{model.patient.nb_interactions} interaction(s) avec soignant.")
 
# ── Construction des frames ────────────────────────────────────────────────
seq = [(h[1], h[2], h[3]) for h in model.historique]   # (node, etat, libelle)
 
COULEUR_ETAT = {
    "TRANSIT":      "#E24B4A",   # rouge
    "ATTENTE_SOIN": "#F5A623",   # orange
    "SOIN":         "#1D9E75",   # vert
    "TERMINE":      "#888888",   # gris
}
 
K = 6   # images par segment de couloir
frames = []
for i in range(len(seq)):
    node, etat, lib = seq[i]
    cur  = np.array(POS[node], float)
    cdoor = porte(node) if TYPE[node] != "transit" else cur
    col  = COULEUR_ETAT.get(etat, "#E24B4A")
 
    if i + 1 < len(seq) and seq[i + 1][0] != node:   # transition
        nxt   = seq[i + 1][0]
        npt   = np.array(POS[nxt], float)
        ndoor = porte(nxt) if TYPE[nxt] != "transit" else npt
        way = [cur]
        if not np.allclose(cur, cdoor): way.append(cdoor)
        if not np.allclose(ndoor, npt): way.append(ndoor)
        way.append(npt)
        for j in range(len(way) - 1):
            for k in range(K):
                a = k / K
                p = way[j] * (1 - a) + way[j + 1] * a
                frames.append((p[0], p[1], "#E24B4A", lib, "TRANSIT"))
    else:                                               # immobile
        frames.append((cur[0], cur[1], col, lib, etat))
 
# ── Marqueurs fixes des soignants ─────────────────────────────────────────
soignant_markers = []
for s in model.soignants:
    x, y = POS[s.salle]
    col  = "#4A90D9" if s.role == "Med" else "#9B59B6"
    soignant_markers.append((x, y, col, s.nom))
 
# ── Animation ─────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 7))
etxt = {
    "TRANSIT":      "se déplace",
    "ATTENTE_SOIN": "en attente soignant",
    "SOIN":         "en soin",
    "TERMINE":      "sorti",
}
 
def draw(f):
    x, y, col, lib, etat = frames[f]
    dessiner_plan(ax, model.G,
                  patient_pos=(x, y, col),
                  soignant_markers=soignant_markers,
                  titre=f"{etxt.get(etat, etat)} — {lib}")
 
ani = animation.FuncAnimation(fig, draw, frames=len(frames), interval=160, repeat=True)
plt.close(fig)
HTML(ani.to_jshtml())
ani.save("plan_balade_soignants.gif", writer=animation.PillowWriter(fps=7))