
from django.contrib import admin
from django.urls import path,include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('schedule/', views.schedule, name='schedule'),
    path('add_appointment/', views.add_appointment_form, name='add_appointment'),
    path('edit_appointment/<int:id>/', views.appointment_form, name='edit_appointment'),
    path('delete_appointment/<int:id>/', views.delete_appointment, name='delete_appointment'),
    path('users/<int:id>', views.medical_information, name='medical_information'),
    path('user/me/', views.my_medical_information, name='my_medical_information'),
    path('users/',views.users,name='users'),
]
