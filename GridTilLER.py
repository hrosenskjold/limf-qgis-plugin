# -*- coding: utf-8 -*-
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingMultiStepFeedback,
    QgsProcessingUtils,
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
            defaultValue=100.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CELL_HEIGHT, 'Cellehøjde (meter)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=100.0))
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
        buffer_dist = self.parameterAsDouble(parameters, self.BUFFER_DISTANCE, context) / 2
        crs = QgsCoordinateReferenceSystem('EPSG:25832')

        # 0. Reprojectér input til EPSG:25832
        input_25832 = processing.run('native:reprojectlayer', {
            'INPUT': parameters[self.INPUT],
            'TARGET_CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # 1. Konvertér projektgrænse-polygon til linje og buffer den
        #    → giver en smal strip langs projektgrænsens yderkant
        boundary_line = processing.run('native:polygonstolines', {
            'INPUT': input_25832,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        boundary_buffered = processing.run('native:buffer', {
            'INPUT': boundary_line,
            'DISTANCE': buffer_dist,
            'SEGMENTS': 5,
            'DISSOLVE': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # 2. Opret fishnet af linjer over projektgrænsens udstrækning
        grid_lines = processing.run('qgis:creategrid', {
            'TYPE': 1,  # Linjer
            'EXTENT': input_25832,
            'HSPACING': cell_width,
            'VSPACING': cell_height,
            'CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # 3. Klip gridlinjer til projektgrænsen
        grid_clipped = processing.run('native:clip', {
            'INPUT': grid_lines,
            'OVERLAY': input_25832,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # 4. Buffer de klippede gridlinjer → smalle strips langs linjerne
        grid_buffered = processing.run('native:buffer', {
            'INPUT': grid_clipped,
            'DISTANCE': buffer_dist,
            'SEGMENTS': 5,
            'DISSOLVE': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # 5. Merge: bufferet projektgrænse + bufferede gridlinjer
        merged = processing.run('native:mergevectorlayers', {
            'LAYERS': [boundary_buffered, grid_buffered],
            'CRS': crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # 6. Dissolve til ét samlet polygon
        dissolved = processing.run('native:dissolve', {
            'INPUT': merged,
            'FIELD': [],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']

        feedback.setCurrentStep(7)

        result = QgsProcessingUtils.mapLayerFromString(dissolved, context)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            result.fields(), QgsWkbTypes.Polygon, crs)

        for feat in result.getFeatures():
            sink.addFeature(feat)

        return {self.OUTPUT: dest_id}

    def createInstance(self):
        return GridTilLER()
