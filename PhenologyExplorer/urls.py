from django.urls import path
from PhenologyExplorer import views

app_name='PhenologyExplorer'

urlpatterns=[
    path('',views.handleSaveSettings,name='index'),
    path('monthly_composite',views.handleMonthlyComposite,name="monthly_composite")
]