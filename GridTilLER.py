# -*- coding: utf-8 -*-
from qgis.core import QgsProcessingAlgorithm


class GridTilLER(QgsProcessingAlgorithm):

    def name(self):
        return 'grid_til_ler'

    def displayName(self):
        return 'Grid til LER'

    def group(self):
        return 'Limfjordssekretariatet tools'

    def groupId(self):
        return 'limf_tools'

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        return {}

    def createInstance(self):
        return GridTilLER()
