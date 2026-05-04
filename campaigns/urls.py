from django.urls import path

from .views import company_application_create, company_application_success

urlpatterns = [
    path("apply/", company_application_create, name="company_application_create"),
    path("apply/success/", company_application_success, name="company_application_success"),
]
