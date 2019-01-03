from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(User)
admin.site.register(Appointment)
admin.site.register(Insurance)
admin.site.register(DoctorInformation)
admin.site.register(Hospital)
