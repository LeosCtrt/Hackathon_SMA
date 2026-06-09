import mesa
import networkx as nx
from core.agents.soignant import SoignantAgent
class Patient(mesa.Agent):
    #Etats possibles :
    #  TRANSIT      -> se déplace vers sa prochaine destination
    #  ATTENTE_SOIN -> arrivé, attend qu'un SoignantAgent le prenne en charge
    #  SOIN         -> soin en cours (géré par le soignant ou en autonome)
    #  TERMINE      -> parcours terminé
 
    def __init__(self, model, parcours, depart="ACC"):
        super().__init__(model)
        self.parcours = parcours        # [(salle, libelle, duree), ...]
        self.node = depart
        self.etat = "TRANSIT"
        self.cible_index = 0
        self.chemin = []
        self.temps_soin_actuel = 0      # durée lue par le soignant (ou auto)
        self.nb_interactions = 0        # soins effectués avec un soignant
 
    @property
    def cible(self):
        return self.parcours[self.cible_index][0]
 
    def step(self):
        if self.etat == "TERMINE":
            return
 
        # ── Soin géré en autonome (pas de soignant dans la salle) ──────────
        if self.etat == "SOIN":
            self.temps_soin_actuel -= 1
            if self.temps_soin_actuel <= 0:
                self.fin_soin(avec_soignant=False)
            return
 
        # ── En attente d'un soignant : ne bouge pas ────────────────────────
        if self.etat == "ATTENTE_SOIN":
            return
 
        # ── TRANSIT : calcul et suivi du plus court chemin ─────────────────
        if self.node == self.cible:
            self._arriver_a_destination()
            return
        if not self.chemin:
            self.chemin = nx.shortest_path(self.model.G, self.node, self.cible)[1:]
        prochain = self.chemin.pop(0)
        self.model.grid.move_agent(self, prochain)
        self.node = prochain
        if self.node == self.cible:
            self._arriver_a_destination()
 
    def _arriver_a_destination(self):
        #A l'arrivée : si un SoignantAgent est présent → ATTENTE_SOIN ;
        #sinon → SOIN autonome (accueil, repos, facturation...).
        self.temps_soin_actuel = self.parcours[self.cible_index][2]
        contenu = self.model.grid.get_cell_list_contents([self.node])
        soignants = [a for a in contenu if isinstance(a, SoignantAgent)]
        if soignants:
            self.etat = "ATTENTE_SOIN"  # le soignant prend la main au prochain step
        else:
            self.etat = "SOIN"          # gestion autonome du timer
 
    def fin_soin(self, avec_soignant=False):
        #Avance vers la prochaine étape du parcours.
        if avec_soignant:
            self.nb_interactions += 1
        self.cible_index += 1
        if self.cible_index >= len(self.parcours):
            self.etat = "TERMINE"
        else:
            self.etat = "TRANSIT"
            self.chemin = []