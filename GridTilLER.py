# -*- coding: utf-8 -*-
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingMultiStepFeedback,
    QgsCoordinateReferenceSystem,
    QgsProcessing,
    QgsWkbTypes,
)
import processing


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

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(7, model_feedback)
        cell_width = self.parameterAsDouble(parameters, self.CELL_WIDTH, context)
        cell_height = self.parameterAsDouble(parameters, self.CELL_HEIGHT, context)
        buffer_dist = self.parameterAsDouble(parameters, self.BUFFER_DISTANCE, context)
        crs = QgsCoordinateReferenceSystem('EPSG:25832')

        # 0. Reprojectér input til EPSG:25832 så alle afstande er i meter
        input_25832 = processing.run('native:reprojectlayer', {
            'INPUT': parameters[self.INPUT],
            'TARGET_CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # 1. Opret grid over projektgrænse
        grid = processing.run('qgis:creategrid', {
            'TYPE': 2,
            'EXTENT': input_25832,
            'HSPACING': cell_width,
            'VSPACING': cell_height,
            'CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # 2. Buffer projektgrænse fuldt
        proj_buffered = processing.run('native:buffer', {
            'INPUT': input_25832,
            'DISTANCE': buffer_dist,
            'SEGMENTS': 5,
            'DISSOLVE': True,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Fratræk original → kun ydre ring (svarende til OUTSIDE_ONLY)
        proj_outer = processing.run('native:difference', {
            'INPUT': proj_buffered,
            'OVERLAY': input_25832,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # 3. Buffer grid, dissolve alt til ét polygon
        grid_buffered = processing.run('native:buffer', {
            'INPUT': grid,
            'DISTANCE': buffer_dist,
            'SEGMENTS': 5,
            'DISSOLVE': True,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # 4. Klip grid-buffer til projektgrænse
        grid_clipped = processing.run('native:clip', {
            'INPUT': grid_buffered,
            'OVERLAY': input_25832,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # 5. Merge ydre ring + klippet grid
        merged = processing.run('native:mergevectorlayers', {
            'LAYERS': [proj_outer, grid_clipped],
            'CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # 6. Opdel multipart til single parts
        result = processing.run('native:multiparttosingleparts', {
            'INPUT': merged,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            result.fields(), QgsWkbTypes.Polygon, crs)

        for feat in result.getFeatures():
            sink.addFeature(feat)

        return {self.OUTPUT: dest_id}

    def createInstance(self):
        return GridTilLER()
