import mesa
from mesa.space import NetworkGrid

from core.plan.plan_hdj import construire_plan_hdj
from core.agents.salle import Salle
from core.agents.soignant import SoignantAgent
from core.agents.patient import Patient

class HopitalModel(mesa.Model):
    #Modèle de l'Hôpital de Jour.
 
    #Soignants instanciés (salle assignée à l'init) :
    # - Dr. Dupont   (Med)     → BMED1   [8h-17h]
    #  - Dr. Martin   (Med)     → BMED2   [8h-17h]
    #  - Dr. Blanc    (Med)     → BCHIR   [8h-17h]
    #  - IDE Bilan    (Paramed) → SOIN    [7h-19h]
    #  - IDE Chimio   (Paramed) → SCHIM   [7h-19h]
    
 
    # Configuration des soignants : (nom, role, salle, h_debut, h_fin)
    CONFIGS_SOIGNANTS = [
        ("Dr. Dupont",  "Med",     "BMED1", 8, 17),
        ("Dr. Martin",  "Med",     "BMED2", 8, 17),
        ("Dr. Blanc",   "Med",     "BCHIR", 8, 17),
        ("IDE Bilan",   "Paramed", "SOIN",  7, 19),
        ("IDE Chimio",  "Paramed", "SCHIM", 7, 19),
    ]
 
    def __init__(self, parcours, seed=42):
        super().__init__(rng=seed)
        self.G = construire_plan_hdj()
        self.grid = NetworkGrid(self.G)
        self.heure_actuelle = 8.0   # 8 h du matin ; 1 step = 10 min
 
        # ── Salles ────────────────────────────────────────────────────────
        for n, d in self.G.nodes(data=True):
            if d["type"] != "transit":
                self.grid.place_agent(Salle(self, n, d["type"], d["capacite"]), n)
 
        # ── Soignants ────────────────────────────────────────────────────
        self.soignants: list[SoignantAgent] = []
        for nom, role, salle, hd, hf in self.CONFIGS_SOIGNANTS:
            ag = SoignantAgent(self, nom, role, salle, hd, hf)
            self.soignants.append(ag)
            self.grid.place_agent(ag, salle)
            print(f"  → {role:8s} {nom:12s} affecté à {salle}")
 
        # ── Patient ───────────────────────────────────────────────────────
        self.patient = Patient(self, parcours, "ACC")
        self.grid.place_agent(self.patient, "ACC")
 
        self.historique = []
        self.running = True
 
    # ──────────────────────────────────────────────────────────────────────
    # Interface "admin" invoquée par SoignantAgent
    # ──────────────────────────────────────────────────────────────────────
 
    def fournir_patient(self, soignant: SoignantAgent):
        #Retourne un patient en ATTENTE_SOIN dans la salle du soignant, ou None.\"\"\"
        for agent in self.grid.get_cell_list_contents([soignant.salle]):
            if isinstance(agent, Patient) and agent.etat == "ATTENTE_SOIN":
                return agent
        return None
 
    def notifier_debut_prestation(self, soignant: SoignantAgent, patient: Patient):
        #Hook appelé quand un soignant commence un soin (extensible)
        pass
 
    def notifier_fin_prestation(self, soignant: SoignantAgent, patient: Patient):
        #Appelé quand le soignant termine : fait avancer le patient.
        patient.fin_soin(avec_soignant=True)
 
    # ──────────────────────────────────────────────────────────────────────
 
    def step(self):
        p = self.patient
        idx = min(p.cible_index, len(p.parcours) - 1)
        self.historique.append((self.steps, p.node, p.etat, p.parcours[idx][1]))
 
        # 1) le patient se déplace ou gère un soin autonome
        p.step()
        # 2) chaque soignant cherche/continue un soin dans sa salle
        for s in self.soignants:
            s.step()
 
        # avance l'horloge (1 step ≈ 10 min)
        self.heure_actuelle += 10 / 60
 
        if p.etat == "TERMINE":
            self.historique.append((self.steps, p.node, "TERMINE", "sortie"))
            self.running = False