from mesa import Agent

class SoignantAgent(Agent):
    #Medecin ou paramédical affecté à une salle fixe de l'HDJ.
 
    def __init__(self, model, nom, role, salle, heure_debut=0, heure_fin=24):
        super().__init__(model)
        self.nom = nom
        self.role = role            # "Med" ou "Paramed"
        self.salle = salle          # nœud du graphe où le soignant est posé
        self.heure_debut = heure_debut
        self.heure_fin = heure_fin
        self.patient_actuel = None
        self.temps_soin_restant = 0
 
    def step(self):
        # ── Vérification des horaires ──────────────────────────────────────
        if (self.model.heure_actuelle < self.heure_debut
                or self.model.heure_actuelle >= self.heure_fin):
            return  # pas en service
 
        # ── Soin en cours : décrémenter le timer ───────────────────────────
        if self.patient_actuel is not None:
            self.temps_soin_restant -= 1
            if self.temps_soin_restant <= 0:
                print(f"[{self.role} {self.nom}] Termine la consultation "
                      f"avec le patient {self.patient_actuel.unique_id}.")
                self.model.notifier_fin_prestation(self, self.patient_actuel)
                self.patient_actuel = None
 
        # ── Cherche un patient en attente dans sa salle ────────────────────
        if self.patient_actuel is None:
            nouveau = self.model.fournir_patient(self)
            if nouveau is not None:
                self.patient_actuel = nouveau
                self.patient_actuel.etat = "SOIN"
                self.temps_soin_restant = nouveau.temps_soin_actuel
                print(f"[{self.role} {self.nom}] Débute la consultation "
                      f"avec le patient {nouveau.unique_id}.")
                self.model.notifier_debut_prestation(self, nouveau)
