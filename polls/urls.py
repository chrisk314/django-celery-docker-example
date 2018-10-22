from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("check/<str:task_id>/", views.check, name="check"),
    path("download/", views.download, name="download"),
]
