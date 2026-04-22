# -*- coding: utf-8 -*-
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsCoordinateReferenceSystem,
    QgsProcessing,
    QgsWkbTypes,
)
from qgis import processing


class GridTilLER(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    CELL_WIDTH = 'CELL_WIDTH'
    CELL_HEIGHT = 'CELL_HEIGHT'
    BUFFER_DISTANCE = 'BUFFER_DISTANCE'

    def name(self):
        return 'grid_til_ler'

    def displayName(self):
        return 'Grid til LER'

    def group(self):
        return 'Limfjordssekretariatet tools'

    def groupId(self):
        return 'limf_tools'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Projektgrænse',
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber(
            self.CELL_WIDTH, 'Cellebredde (meter)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=500.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CELL_HEIGHT, 'Cellehøjde (meter)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=500.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.BUFFER_DISTANCE, 'Bufferafstand (meter)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=1.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Til LER søgning'))

    def processAlgorithm(self, parameters, context, feedback):
        cell_width = self.parameterAsDouble(parameters, self.CELL_WIDTH, context)
        cell_height = self.parameterAsDouble(parameters, self.CELL_HEIGHT, context)
        buffer_dist = self.parameterAsDouble(parameters, self.BUFFER_DISTANCE, context)
        crs = QgsCoordinateReferenceSystem('EPSG:25832')

        feedback.setProgressText('Opretter grid...')

        # 1. Opret grid over projektgrænse
        grid = processing.run('qgis:creategrid', {
            'TYPE': 2,
            'EXTENT': parameters[self.INPUT],
            'HSPACING': cell_width,
            'VSPACING': cell_height,
            'CRS': crs,
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        feedback.setProgressText('Bufferer projektgrænse (ydersiden)...')

        # 2. Buffer projektgrænse fuldt, fratræk original → kun ydre ring (svarende til OUTSIDE_ONLY)
        proj_buffered = processing.run('native:buffer', {
            'INPUT': parameters[self.INPUT],
            'DISTANCE': buffer_dist,
            'SEGMENTS': 5,
            'DISSOLVE': True,
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        proj_outer = processing.run('native:difference', {
            'INPUT': proj_buffered,
            'OVERLAY': parameters[self.INPUT],
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        feedback.setProgressText('Bufferer grid og klip til projektgrænse...')

        # 3. Buffer grid, dissolve alt til ét polygon
        grid_buffered = processing.run('native:buffer', {
            'INPUT': grid,
            'DISTANCE': buffer_dist,
            'SEGMENTS': 5,
            'DISSOLVE': True,
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        # 4. Klip grid-buffer til projektgrænse
        grid_clipped = processing.run('native:clip', {
            'INPUT': grid_buffered,
            'OVERLAY': parameters[self.INPUT],
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        feedback.setProgressText('Merger lag og oprydder geometrier...')

        # 5. Merge ydre ring + klippet grid
        merged = processing.run('native:mergevectorlayers', {
            'LAYERS': [proj_outer, grid_clipped],
            'CRS': crs,
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        # 6. Opdel multipart til single parts (svarende til ArcGIS Dissolve by OBJECTID + SINGLE_PART)
        result = processing.run('native:multiparttosingleparts', {
            'INPUT': merged,
            'OUTPUT': 'memory:'
        }, context=context, feedback=feedback)['OUTPUT']

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            result.fields(), QgsWkbTypes.Polygon, crs)

        for feat in result.getFeatures():
            sink.addFeature(feat)

        return {self.OUTPUT: dest_id}

    def createInstance(self):
        return GridTilLER()
