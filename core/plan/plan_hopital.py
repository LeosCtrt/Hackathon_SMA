import numpy as np
import networkx as nx
from matplotlib.patches import Rectangle, FancyBboxPatch

POS = {
    "CHM5": (22, 72), "CHM6": (38, 50), "CHM11": (46, 52),
    "CHM3": (86, 66), "CHM4": (95, 40), "CHM1": (176, 66), "CHM2": (178, 40),
    "PATIO": (151, 53),
    "ACC": (10, 84), "SEC": (10, 74), "SAN1": (10, 64), "SAN2": (10, 56),
    "ESC13": (30, 63),
    "PLAT": (54, 80), "STKC": (66, 80), "REUN": (78, 80), "CADR": (90, 80),
    "CH01": (104, 80), "SDE01": (104, 90), "CH02": (118, 80), "SDE02": (118, 90),
    "DECH": (58, 55), "LSAL": (58, 45),
    "LPRO": (74, 58), "STKM": (86, 58), "BAIN1": (98, 58), "DET": (110, 58),
    "VID": (74, 48), "DECO": (86, 48),
    "MEN": (22, 44), "BMED1": (54, 26), "BCHIR": (66, 26), "BMED2": (78, 26),
    "OFF": (92, 26), "EDU": (104, 26), "DIET": (116, 26),
    "CH06": (130, 26), "SDE06": (130, 16), "CH07": (142, 26), "SDE07": (142, 16),
    "CH08": (154, 26), "SDE08": (154, 16),
    "CH03": (158, 80), "SDE03": (158, 90), "SCHIR": (182, 82),
    "CH04": (202, 80), "SDE04": (202, 90), "CH05": (216, 80), "SDE05": (216, 90),
    "PINF1": (140, 62), "SOIN": (152, 63),
    "SCHIM": (182, 24), "CH09": (166, 26), "SDE09": (166, 16),
    "CH10": (202, 26), "SDE10": (202, 16), "CH11": (216, 26), "SDE11": (216, 16),
    "PINF2": (150, 44), "ESC12": (210, 8),
    "SDECHIR": (182, 93), "SDECHIM": (182, 15),
}
 
BANDES = {
    "CHM5":  ((22, 56), (22, 88)), "CHM6":  ((22, 50), (46, 50)),
    "CHM11": ((46, 42), (46, 66)), "CHM3":  ((46, 66), (132, 66)),
    "CHM4":  ((46, 40), (158, 40)), "CHM1":  ((132, 66), (220, 66)),
    "CHM2":  ((150, 40), (220, 40)),
}
 
ATTACH = {
    "CHM5":  ["ACC", "SEC", "SAN1", "SAN2"],
    "CHM6":  ["MEN"],
    "CHM11": ["ESC13", "DECH", "LSAL"],
    "CHM3":  ["PLAT", "STKC", "REUN", "CADR", "CH01", "CH02",
              "LPRO", "STKM", "BAIN1", "DET"],
    "CHM4":  ["VID", "DECO", "BMED1", "BCHIR", "BMED2",
              "OFF", "EDU", "DIET", "CH06", "CH07", "CH08"],
    "CHM1":  ["CH03", "SCHIR", "CH04", "CH05", "PINF1", "SOIN"],
    "CHM2":  ["SCHIM", "CH09", "CH10", "CH11", "PINF2", "ESC12"],
}
 
LIAISONS = [("CHM5", "CHM6"), ("CHM5", "CHM3"), ("CHM6", "CHM11"),
            ("CHM11", "CHM3"), ("CHM11", "CHM4"), ("CHM3", "CHM4"),
            ("CHM3", "CHM1"), ("CHM4", "CHM2"), ("CHM1", "CHM2"),
            ("CHM1", "PATIO"), ("CHM2", "PATIO")]
 
PRIVE = [(f"CH{i:02d}", f"SDE{i:02d}") for i in range(1, 12)] + \
        [("SCHIR", "SDECHIR"), ("SCHIM", "SDECHIM"), ("SEC", "ACC")]
 
PATIO_ADJ = [("PATIO", "PINF1"), ("PATIO", "SOIN"), ("PATIO", "PINF2")]
 
LABELS = {
    "CHM5": "C5", "CHM6": "C6", "CHM11": "C11", "CHM3": "C3", "CHM4": "C4",
    "CHM1": "C1", "CHM2": "C2", "PATIO": "Patio",
    "ACC": "Accueil", "SEC": "Secretariat\\nfacturation",
    "SAN1": "Sanit. 1", "SAN2": "Sanit. 2",
    "ESC13": "ESC13",
    "PLAT": "Salle\\nplatre", "STKC": "Stockage\\nconso", "REUN": "Salle\\nreunion",
    "CADR": "Bureau\\ncadre", "LPRO": "Linge\\npropre", "STKM": "Stockage\\nmateriel",
    "BAIN1": "Salle de\\nbain", "DET": "Salle\\ndetente", "DECH": "Dechets",
    "LSAL": "Linge\\nsale", "VID": "Vidoir", "DECO": "Decontam.",
    "MEN": "Local\\nmenage", "BMED1": "Bureau\\nmedecine", "BCHIR": "Bureau\\nchirurgie",
    "BMED2": "Bureau\\nmedecin", "OFF": "Office\\nalim.", "EDU": "Salle\\neducation",
    "DIET": "Bureau\\ndietet.", "SCHIR": "Salle chirurgie\\n4 fauteuils",
    "SCHIM": "Salle chimio\\n4 fauteuils", "PINF1": "Poste IDE 1",
    "PINF2": "Poste IDE 2", "SOIN": "Salle\\nde soins", "ESC12": "ESC12",
    "SDECHIR": "SDE", "SDECHIM": "SDE",
    **{f"CH{i:02d}": f"Chambre\\n{i}" for i in range(1, 12)},
    **{f"SDE{i:02d}": "SDE" for i in range(1, 12)},
}
 
TYPE = {c: "transit" for c in BANDES}
TYPE["PATIO"] = "transit"
for n in ["ACC", "SEC"]: TYPE[n] = "administratif"
for n in ["SAN1", "SAN2"]: TYPE[n] = "sanitaire"
for n in ["ESC13", "ESC12"]: TYPE[n] = "escalier"
for n in ["PLAT", "BAIN1", "DET", "EDU",
          "SCHIR", "SCHIM", "PINF1", "PINF2", "SOIN"]: TYPE[n] = "soin"
for n in ["REUN", "CADR", "BMED1", "BCHIR", "BMED2", "DIET"]: TYPE[n] = "staff"
for n in ["STKC", "STKM", "LPRO", "LSAL", "DECH", "VID", "DECO", "OFF", "MEN"]:
    TYPE[n] = "logistique"
for i in range(1, 12): TYPE[f"CH{i:02d}"] = "repos"
for i in range(1, 12): TYPE[f"SDE{i:02d}"] = "sde"
TYPE["SDECHIR"] = "sde"; TYPE["SDECHIM"] = "sde"
 
CAP = {"soin": 4, "repos": 1, "administratif": 2, "sanitaire": 2, "staff": 1,
       "logistique": 0, "sde": 1, "escalier": 0, "transit": 99}
COULEURS = {"soin": "#F0997B", "repos": "#AFCBEC", "administratif": "#B7DA8C",
            "sanitaire": "#D6E9BC", "staff": "#F7CE84", "logistique": "#E2E0D8",
            "sde": "#DDEAF6", "escalier": "#FFFFFF", "transit": "#DAD8CE"}
 
 
def construire_plan_hdj() -> nx.Graph:
    G = nx.Graph(name="Plan HDJ complet")
    for n, t in TYPE.items():
        G.add_node(n, type=t, capacite=CAP[t], pos=POS[n], label=LABELS[n])
    G.add_edges_from(LIAISONS)
    for cor, salles in ATTACH.items():
        for s in salles:
            G.add_edge(cor, s)
    G.add_edges_from(PRIVE)
    G.add_edges_from(PATIO_ADJ)
    return G
 
 
def _proj(p, seg):
    a, b = np.array(seg[0], float), np.array(seg[1], float)
    p = np.array(p, float)
    t = np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0, 1)
    return a + t * (b - a)
 
 
def porte(node):
    #Point d'accroche d'une salle sur la bande de son couloir.
    for cor, salles in ATTACH.items():
        if node in salles:
            return _proj(POS[node], BANDES[cor])
    return np.array(POS[node], float)
 
 
def dessiner_plan(ax, G, patient_pos=None, soignant_markers=None, titre=""):
    #Trace le plan de l'HDJ.
    #soignant_markers : liste de (x, y, couleur) pour les soignants.
    #patient_pos      : (x, y, couleur) pour l'etoile du patient.
    ax.clear()
    ax.add_patch(Rectangle((2, 2), 224, 100, fill=False, lw=2.5, ec="#444"))
    ax.add_patch(Rectangle((138, 46), 26, 14, fc="#EAF3DE", ec="#9BB36B", lw=1))
    ax.text(151, 53, "Patio", ha="center", va="center", fontsize=7, color="#5A7032")
    for seg in BANDES.values():
        (x0, y0), (x1, y1) = seg
        ax.plot([x0, x1], [y0, y1], color="#DAD8CE", lw=11,
                solid_capstyle="round", zorder=1)
    for a, b in [("CHM1", "PATIO"), ("CHM2", "PATIO")]:
        ax.plot([POS[a][0], POS[b][0]], [POS[a][1], POS[b][1]],
                color="#DAD8CE", lw=8, solid_capstyle="round", zorder=1)
    for cor, salles in ATTACH.items():
        for s in salles:
            d = porte(s)
            ax.plot([d[0], POS[s][0]], [d[1], POS[s][1]],
                    color="#CFCDC4", lw=2.5, solid_capstyle="round", zorder=1)
    for u, v in PRIVE:
        ax.plot([POS[u][0], POS[v][0]], [POS[u][1], POS[v][1]],
                color="#CFCDC4", lw=2, ls=":", zorder=1)
    for u, v in PATIO_ADJ:
        ax.plot([POS[u][0], POS[v][0]], [POS[u][1], POS[v][1]],
                color="#9BB36B", lw=1.5, ls=(0, (2, 2)), zorder=1)
    for n, t in TYPE.items():
        if t == "transit":
            continue
        x, y = POS[n]
        if n in ("SCHIR", "SCHIM"):
            w, h = 16, 9
        elif t == "sde":
            w, h = 8.5, 5.5
        else:
            w, h = 11, 7
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                     boxstyle="round,pad=0.2,rounding_size=1",
                     fc=COULEURS[t], ec="#555", lw=0.8, zorder=2))
        ax.text(x, y, LABELS[n], ha="center", va="center",
                fontsize=4.2 if t == "sde" else 4.8, zorder=3)
    for cor in BANDES:
        x, y = POS[cor]
        ax.text(x, y, LABELS[cor], ha="center", va="center", fontsize=6,
                color="#777", fontweight="bold", zorder=3)
    # Soignants (losanges fixes, bleu=Med, violet=Paramed)
    if soignant_markers:
        for sx, sy, scol, nom in soignant_markers:
            ax.scatter([sx], [sy], s=220, c=scol, marker="D",
                       edgecolors="#222", linewidths=0.8, zorder=5)
            ax.text(sx, sy - 4.5, nom, ha="center", va="top",
                    fontsize=3.5, color="#222", zorder=5)
    # Patient (etoile)
    if patient_pos is not None:
        ax.scatter([patient_pos[0]], [patient_pos[1]], s=460, c=patient_pos[2],
                   marker="*", edgecolors="black", linewidths=1.3, zorder=6)
    ax.set_xlim(-2, 230); ax.set_ylim(-2, 106)
    ax.set_aspect("equal"); ax.axis("off")
    if titre:
        ax.set_title(titre, fontsize=11)