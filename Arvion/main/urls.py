from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path("main/", views.arvion, name="arvion"),  
    path("about/", views.about_project, name="about_project"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("terms-privacy/", views.terms_privacy, name="terms_privacy"),
    path('settings/', views.settings_view, name='settings'), 
    path("security/", views.security, name="security"),
    path("status/", views.status, name="status"),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_page_view, name='login'), 
    path('profile/', views.profile_view, name='profile'),path('find-hospital/', views.find_hospital, name='find_hospital'),
    path('profile/<uuid:profile_id>/', views.public_profile_view, name='public_profile'),
    path('qr-code/', views.qr_code_view, name='qr_code'),
    path('logout/', LogoutView.as_view(next_page='arvion'), name='logout'),
    path('api/login/', views.login_api_view, name='login_api_view'),
    path('search/photo/', views.search_patient_by_photo, name='search_patient_by_photo'),
    path('patient/<int:user_id>/', views.patient_details_view, name='patient_details'),


]