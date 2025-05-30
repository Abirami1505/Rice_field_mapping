import os
import environ
from django.conf import settings
import ee

env=environ.Env()
env.read_env(os.path.join(settings.BASE_DIR,".env"))

EE_ACCOUNT = os.environ.get("EE_ACCOUNT")
EE_CREDENTIAL = os.environ.get("EE_CREDENTIALS")
print(EE_CREDENTIAL)

try:
    EE_CREDENTIALS = ee.ServiceAccountCredentials(EE_ACCOUNT,EE_CREDENTIAL)
    print(EE_CREDENTIALS)
    print("GEE authentication successful")
except Exception as e:
    EE_CREDENTIALS=None
    print("Cannot authenticate GEE:",str(e))

