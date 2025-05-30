from django.apps import AppConfig
import ee
from utils.credentials import EE_CREDENTIALS

class SupervisedclassificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'SupervisedClassification'

    def ready(self):
        ee.Initialize(EE_CREDENTIALS)