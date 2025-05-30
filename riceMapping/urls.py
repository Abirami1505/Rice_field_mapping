"""
URL configuration for riceMapping project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include,re_path
from .views import home,get_task_with_id,get_tasks,handle_download_file

urlpatterns = [
    path('',home,name="home"),
    path('admin/', admin.site.urls),
    path('phenology/',include('PhenologyExplorer.urls')),
    path('empirical/',include('EmpericalThreshold.urls')),
    path('classification/',include('SupervisedClassification.urls')),

    path("tasks/<str:id>",get_task_with_id),
    path("tasks/",get_tasks),
    path("download/<str:id>",handle_download_file),

    re_path(r"^$", home),
    re_path(r"^(?:.*)/?$", home),
]
