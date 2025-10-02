from django.urls import path
from . import views

urlpatterns = [
    path("", views.splash, name="splash"),  # Splash page
    path("dashboard/", views.dashboard, name="dashboard"),
    path("webhook/gh/", views.gh_webhook, name="gh_webhook"),
    # path("pr/<str:project>/<int:number>/", views.pr_detail, name="pr_detail"),
    path("pr/<str:user>/<str:project>/<int:number>/", views.pr_detail, name="pr_detail")
]
