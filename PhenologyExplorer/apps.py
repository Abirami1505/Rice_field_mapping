from django.apps import AppConfig

import ee
from utils.credentials import EE_CREDENTIALS

class PhenologyexplorerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'PhenologyExplorer'

    def ready(self):
        self.initialize()

    def initialize(self):
        ee.Initialize(EE_CREDENTIALS)
