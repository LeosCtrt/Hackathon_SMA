import mesa

class Salle(mesa.Agent):
    def __init__(self, model, nom, type_salle, capacite):
        super().__init__(model)
        self.nom = nom; self.type_salle = type_salle
        self.capacite = capacite; self.occupes = 0