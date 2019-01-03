
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import AbstractUser, Group

class Insurance(models.Model):
    policy_number = models.CharField(max_length=200, null=True)
    company = models.CharField(max_length=200, null=True)

    def __repr__(self):
        return "{0} with {1}".format(self.policy_number, self.company)

class EmergencyContact(models.Model):
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=30)
    relationship = models.CharField(max_length=30)

class MedicalInformation(models.Model):
    SEX_CHOICES = (
        'Female',
        'Male',
        'Intersex',
    )
    sex = models.CharField(max_length=50)
    insurance = models.ForeignKey(Insurance,on_delete=models.CASCADE, null=True)
    medications = models.CharField(max_length=200, null=True)
    allergies = models.CharField(max_length=200, null=True)
    medical_conditions = models.CharField(max_length=200, null=True)
    family_history = models.CharField(max_length=200, null=True)
    additional_info = models.CharField(max_length=400, null=True)

    def __repr__(self):
        return (("Sex: {0}, Insurance: {1}, Medications: {2}, Allergies: {3}, " +
                "Medical Conditions: {4}, Family History: {5}," +
                " Additional Info: {6}").format(
                    self.sex, repr(self.insurance), self.medications,
                    self.allergies, self.medical_conditions,
                    self.family_history, self.additional_info
                ))


class Hospital(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    state = models.CharField(max_length=2)
    zipcode = models.CharField(max_length=20)

    def __repr__(self):
        # "St. Jude Hospital at 1 Hospital Road, Waterbury, CT 06470"
        return ("%s at %s, %s, %s %s" % self.name, self.address, self.city,
                self.state, self.zipcode)

class DoctorInformation(models.Model):
    specialisation = models.CharField(max_length=100,null=True)
    years_of_experience = models.CharField(max_length=2,null=True)
    fee = models.CharField(max_length=5,null=True)
    degree = models.CharField(max_length=200,null=True)
    visit_days = models.CharField(max_length=200,null=True)
    two_shift = models.CharField(max_length=10,null=True)
    first_shift_start = models.CharField(max_length=10,null=True)
    first_shift_end = models.CharField(max_length=10,null=True)
    second_shift_start = models.CharField(max_length=10,null=True)
    second_shift_end = models.CharField(max_length=10,null=True)

    VISIT_DAYS = (
        'Monday',
        'Tuesday',
        'Wednesday',
        'Thursday',
        'Friday',
        'Saturday',
        'Sunday',
    )

    SPECIALISATION = (
        'Dentist',
        'Gynecologist/Obstetrician',
        'General Physician',
        'Dermatologist',
        'Ear-Nose-Throat(ENT)',
        'Homoeopath',
        'Ayurveda',
    )

    TWO_DAYS_SHIFT = (
        'Yes',
        'No',
    )

    def __repr__(self):
        return (("specialisation: {0}, years_of_experience: {1}, fee: {2}, degree: {3}, " +
                "visit_days : {4}, two_shift: {5}," +
                "first_shift_start: {6}, first_shift_end: {7}" +
                "second_shift_start: {8}, second_shift_end: {9}").format(
                    self.specialisation, self.years_of_experience,
                    self.fee, self.degree, self.visit_days, self.two_shift,
                    self.first_shift_start, self.first_shift_end,
                    self.second_shift_start,self.second_shift_end
                ))


class User(AbstractUser):
    date_of_birth = models.DateField(null=True)
    phone_number = models.CharField(max_length=30)
    medical_information = models.ForeignKey(MedicalInformation, null=True,on_delete=models.CASCADE)
    emergency_contact = models.ForeignKey(EmergencyContact, null=True,on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital,null=True,on_delete=models.CASCADE)
    doctor_information = models.ForeignKey(DoctorInformation,null=True,on_delete=models.CASCADE)

    REQUIRED_FIELDS = ['phone_number', 'email', 'first_name',
                       'last_name']

    def all_patients(self):
        """
        Returns all patients relevant for a given user.
        If the user is a doctor:
            Returns all patients with active appointments with the doctor.
        If the user is a patient:
            Returns themself.
        If the user is an admin:
            Returns all patients in the database.
        :return:
        """
        if self.is_superuser or self.is_doctor():
            # Admins and doctors can see all users as patients.
            return Group.objects.get(name='Patient').user_set.all()
        else:
            # Users can only see themselves.
            return User.objects.filter(pk=self.pk)

    def can_edit_user(self, user):
        return user == self      \
            or self.is_superuser \
            or user.is_patient() \
            and self.is_doctor()


    def active_patients(self):
        """
        Same as all_patients, but only patients that are active.
        :return: All active patients relevant to the current user.
        """
        return self.all_patients().filter(is_active=True)


    def schedule(self):
        """
        :return: All appointments for which this person is needed.
        """
        if self.is_superuser:
            return Appointment.objects
        elif self.is_doctor():
            # Doctors see all appointments for which they are needed.
            return Appointment.objects.filter(doctor=self)
        # Patients see all appointments
        return Appointment.objects.filter(patient=self)

    def upcoming_appointments(self):
        date = timezone.now()
        start_week = date - timedelta(date.weekday())
        end_week = start_week + timedelta(7)
        return self.schedule().filter(date__range=[start_week, end_week])

    def is_patient(self):
        """
        :return: True if the user belongs to the Patient group.
        """
        return self.is_in_group("Patient")

    def is_doctor(self):
        """
        :return: True if the user belongs to the Doctor group.
        """
        return self.is_in_group("Doctor")

    def is_in_group(self, group_name):
        """
        :param group_name: The group within which to check membership.
        :return: True if the user is a member of the group provided.
        """
        try:
            return (Group.objects.get(name=group_name)
                         .user_set.filter(pk=self.pk).exists())
        except ValueError:
            return False

    def group(self):
        return self.groups.first()

    def is_free(self, date, duration):
        """
        Checks the user's schedule for a given date and duration to see if
        the user does not have an appointment at that time.
        :param date:
        :param duration:
        :return:
        """
        schedule = self.schedule().all()
        end = date + timedelta(minutes=duration)
        for appointment in schedule:
            # If the dates intersect (meaning one starts while the other is
            # in progress) then the person is not free at the provided date
            # and time.
            if (date <= appointment.date <= end or
                    appointment.date <= date <= appointment.end()):
                return False
        return True


class Appointment(models.Model):
    patient = models.ForeignKey(User, related_name='patient_appointments',on_delete=models.CASCADE)
    doctor = models.ForeignKey(User, related_name='doctor_appointments',on_delete=models.CASCADE)
    date = models.DateTimeField()
    duration = models.IntegerField()

    def end(self):
        """
        :return: A datetime representing the end of the appointment.
        """
        return self.date + timedelta(minutes=self.duration)

    def __repr__(self):
        return '{0} minutes on {1}, {2} with {3}'.format(self.duration, self.date,
                                                         self.patient, self.doctor)
