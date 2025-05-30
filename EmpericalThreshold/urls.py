from django.urls import path
from . import views

app_name='EmpericalThreshold'

urlpatterns=[
    path('',views.run_algorithm,name="set_params"),
    path('export',views.handle_export_result,name="export")
]