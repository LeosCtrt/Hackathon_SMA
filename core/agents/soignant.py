from mesa import Agent

class SoignantAgent(Agent):
    """Classe unique pour les médecins et paramédicaux."""
    def __init__(self, unique_id, model, role, heure_debut, heure_fin):
        super().__init__(unique_id, model)
        self.role = role #Med ou Paramed
        self.heure_debut = heure_debut
        self.heure_fin = heure_fin
        
        self.patient_actuel = None
        self.temps_soin_restant = 0

    def step(self):
        #Vérification des horaires
        if self.model.heure_actuelle < self.heure_debut or self.model.heure_actuelle >= self.heure_fin:
            return #N'est pas en servive

        #Soin en cours
        if self.patient_actuel is not None:
            self.temps_soin_restant -= 1
            if self.temps_soin_restant <= 0:
                # Fin de la prestation et transmission de l'info
                print(f"[{self.role} {self.unique_id}] Termine la consultation avec le patient {self.patient_actuel.unique_id}.")
                self.model.admin.notifier_fin_prestation(self, self.patient_actuel)
                self.patient_actuel = None
        
        #Nouveau patient si le soignant est libre
        if self.patient_actuel is None:
            nouveau_patient = self.model.admin.fournir_patient(self)
            
            if nouveau_patient is not None:
                self.patient_actuel = nouveau_patient
                self.patient_actuel.etat = "SOIN"
                self.temps_soin_restant = self.patient_actuel.temps_soin
                
                print(f"[{self.role} {self.unique_id}] Débute la consultation avec le patient {nouveau_patient.unique_id}.")
                self.model.admin.notifier_debut_prestation(self, self.patient_actuel)
