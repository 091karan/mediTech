from django.shortcuts import render, redirect, get_object_or_404
from django.utils import dateparse
from django.core.exceptions import PermissionDenied
from django.contrib.admin.models import LogEntry
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.db.models import Max
from . import form_utilities
from .form_utilities import *
from . import checks
from .models import *
import datetime
import json
import time



def login_view(request):
    """
    Presents a simple form for logging in a user.
    If requested via POST, looks for the username and password,
    and attempts to log the user in. If the credentials are invalid,
    it passes an error message to the context which the template will
    render using a Bootstrap alert.

    :param request: The Django request object.
    :return: The rendered 'login' page.
    """
    context = {'navbar':'login'}
    if request.POST:
        user, message = login_user_from_form(request, request.POST)
        if user:
            return render(request,'health/home.html')
        elif message:
            context['error_message'] = message
    return render(request, 'health/login.html', context)


def login_user_from_form(request, body):
    """
    Validates a user's login credentials and returns a tuple
    containing either a valid, logged-in user or a failure
    message.

    Checks if all fields were supplied, then attempts to authenticate,
    then checks if the 'remember' checkbox was checked. If it was, sets
    the cookie's expiration to 0, meaning it will be invalidated when the
    session ends.

    :param request: The Django request object.
    :return: The rendered 'login' page.
    """
    email = body.get("email")
    password = body.get("password")
    if not all([email, password]):
        return None, "You must provide an email and password."
    email = email.lower()  # all emails are lowercase in the database.
    user = authenticate(username=email, password=password)
    remember = body.get("remember")
    if user is None:
        return None, "Invalid username or password."
    login(request, user)
    if remember is not None:
        request.session.set_expiry(0)
    return user, None


def logout_view(request):
    """
    Logs the user out and redirects the user to the login page.
    :param request: The Django request.
    :return: A 301 redirect to the login page.
    """
    logout(request)
    return render(request,'health/login.html')


def signup(request):
    """
    Presents a simple signup page with a form of all the required
    fields for new users.
    Uses the full_signup_context function to populate a year/month/day picker
    and, if the user was created successfully, prompts the user to log in.
    :param request:
    :return:
    """
    context = full_signup_context(None)
    context['is_signup'] = True
    if request.POST:
        user, message = handle_user_form(request, request.POST)
        if user:
            addition(request, user)
            if request.user.is_authenticated:
                return redirect('signup')
            else:
                return render(request,'health/login.html')
        elif message:
            context['error_message'] = message
    context['navbar'] = 'signup'
    return render(request, 'health/signup.html', context)


def full_signup_context(user):
    """
    Returns a dictionary containing valid years, months, days, hospitals,
    and groups in the database.
    """
    return {
        "year_range": reversed(range(1900, datetime.date.today().year + 1)),
        "day_range": range(1, 32),
        "months": [
            "Jan", "Feb", "Mar", "Apr",
            "May", "Jun", "Jul", "Aug",
            "Sep", "Oct", "Nov", "Dec"
        ],
        "years" : range(1,100),
        "hospitals": Hospital.objects.all(),
        "groups": Group.objects.all(),
        "sexes": MedicalInformation.SEX_CHOICES,
        "specialisation" : DoctorInformation.SPECIALISATION,
        "visit_days": DoctorInformation.VISIT_DAYS,
        "shifts": ["Yes","No"],
        "times": [
            "7AM","7.30AM","8AM","8.30AM","9AM","9.30AM","10AM","10.30AM",
            "11AM","11.30AM","12PM","12.30PM","1PM","1.30PM","2PM","2.30PM",
            "3PM","3.30PM","4PM","4.30PM","5PM","5.30PM","6PM","6.30PM",
            "7PM","7.30PM","8PM","8.30PM","9PM","9.30PM","10PM","10.30PM","11PM","11.30PM",
            "12AM","12.30AM","1AM","1.30AM","2AM","2.30AM","3AM","3.30AM",
            "4AM","4.30AM","5AM","5.30AM","6AM","6.30AM"
        ],
        "user_sex_other": (user and user.medical_information and
            user.medical_information.sex not in MedicalInformation.SEX_CHOICES)
    }

@login_required(login_url = "login")
def my_medical_information(request):
    """
    Gets the primary key of the current user and redirects to the medical_information view
    for the logged-in user.
    :param request:
    :return:
    """
    return medical_information(request, request.user.pk)


@login_required(login_url = "login")
def medical_information(request, user_id):
    """
    Checks if the logged-in user has permission to modify the requested user.
    If not, raises a PermissionDenied which Django catches by redirecting to
    a 403 page.

    If requested via GET:
        Renders a page containing all the user's fields pre-filled-in
        with their information.
    If requested via POST:
        modifies the values and redirects to the same page, with the new values.
    :param request: The Django request.
    :param user_id: The user id being requested. This is part of the URL:
    /users/<user_id>/
    :return:
    """
    requested_user = get_object_or_404(User, pk=user_id)
    is_editing_own_medical_information = requested_user == request.user
    if not is_editing_own_medical_information and not\
            request.user.can_edit_user(requested_user):
        raise PermissionDenied

    context = full_signup_context(requested_user)

    if request.POST:
        user, message = handle_user_form(request, request.POST, user=requested_user)
        if user:
            return redirect('medical_information', user.pk)
        elif message:
            context['error_message'] = message

    context["requested_user"] = requested_user
    context["is_patient"] = requested_user.is_patient()
    context["user"] = request.user
    context["requested_hospital"] = requested_user.hospital
    context['is_signup'] = False
    context["navbar"] = "my_medical_information" if is_editing_own_medical_information else "medical_information"
    return render(request, 'health/medical_information.html', context)


def handle_user_form(request, body, user=None):
    """
    Creates a user and validates all of the fields, in turn.
    If there is a failure in any validation, the returned tuple contains
    None and a failure message.
    If validation succeeds and the user can be created, then the returned tuple
    contains the user and None for a failure message.
    :param body: The POST body from the request.
    :return: A tuple containing the User if successfully created,
             or a failure message if the operation failed.
    """
    password = body.get("password")
    first_name = body.get("first_name")
    last_name = body.get("last_name")

    email = body.get("email")
    group = body.get("group")
    patient_group = Group.objects.get(name='Patient')
    group = Group.objects.get(pk=int(group)) if group else patient_group
    is_patient = group == patient_group
    is_doctor = not is_patient
    phone = form_utilities.sanitize_phone(body.get("phone_number"))
    month = int(body.get("month"))
    day = int(body.get("day"))
    year = int(body.get("year"))
    date = datetime.date(month=month, day=day, year=year)
    hospital_key = body.get("hospital")
    hospital = Hospital.objects.get(pk=int(hospital_key)) if hospital_key else None
    policy = body.get("policy")
    company = body.get("company")
    sex = body.get("sex")
    other_sex = body.get("other_sex")
    validated_sex = sex if sex in MedicalInformation.SEX_CHOICES else other_sex
    medications = body.get("medications")
    allergies = body.get("allergies")
    medical_conditions = body.get("medical_conditions")
    family_history = body.get("family_history")
    additional_info = body.get("additional_info")
    specialisation = body.get("specialisation")
    years_of_experience = body.get("years_of_experience")
    fee = body.get("fee")
    degree = body.get("degree")
    visit_days = body.get("visit_days")
    two_shift = body.get("two_shift")
    first_shift_start = body.get("first_shift_start")
    first_shift_end = body.get("first_shift_end")
    second_shift_start = body.get("second_shift_start") if two_shift=="Yes" else ""
    second_shift_end = body.get("second_shift_end") if two_shift=="Yes" else ""

    if not all([first_name, last_name, email, phone,
                month, day, year, date]):
        return None, "All fields are required."
    email = email.lower()  # lowercase the email before adding it to the db.
    if not form_utilities.email_is_valid(email):
        return None, "Invalid email."
    if (user and user.is_patient() and not user.is_superuser) and not all([company, policy]):
        return None, "Insurance information is required."
    if user:
        if(1):
            print("hello")
        elif(2):
            print("hello2")
        user.email = email
        user.phone_number = phone
        user.first_name = first_name
        user.last_name = last_name
        user.date_of_birth = date
        if is_patient and user.medical_information is not None:
            user.medical_information.sex = validated_sex
            user.medical_information.medical_conditions = medical_conditions
            user.medical_information.family_history = family_history
            user.medical_information.additional_info = additional_info
            user.medical_information.allergies = allergies
            user.medical_information.medications = medications
            if user.medical_information.insurance:
                user.medical_information.insurance.policy_number = policy
                user.medical_information.insurance.company = company
                user.medical_information.insurance.save()
            else:
                user.medical_information.insurance = Insurance.objects.create(
                    policy_number=policy,
                    company=company
                )
                addition(request, user.medical_information.insurance)
            user.medical_information.save()
            change(request, user.medical_information, 'Changed fields.')
        if user.is_patient() and user.medical_information is None:
            insurance = Insurance.objects.create(policy_number=policy,
                                                 company=company)
            addition(request, insurance)
            medical_information = MedicalInformation.objects.create(
                allergies=allergies, family_history=family_history,
                sex=validated_sex, medications=medications,
                additional_info=additional_info, insurance=insurance,
                medical_conditions=medical_conditions
            )
            addition(request, user.medical_information)
            user.medical_information = medical_information

        if is_doctor and user.doctor_information is not None:
            print("HELLLOOO")
            user.doctor_information.specialisation = specialisation
            user.doctor_information.years_of_experience = years_of_experience
            user.doctor_information.fee = fee
            user.doctor_information.degree = degree
            user.doctor_information.visit_days = visit_days
            user.doctor_information.two_shift = two_shift
            user.doctor_information.first_shift_start = first_shift_start
            user.doctor_information.first_shift_end = first_shift_end
            user.doctor_information.second_shift_start = second_shift_start
            user.doctor_information.second_shift_end = second_shift_end
            user.doctor_information.save()
            change(request, user.doctor_information, 'Changed fields.')

        if is_doctor and user.doctor_information is None:
            print("helloooo")
            doctor_information = DoctorInformation.objects.create(specialisation=specialisation,
            years_of_experience=years_of_experience,fee=fee,degree=degree,visit_days=visit_days,
            two_shift=two_shift,first_shift_start=first_shift_start,first_shift_end=first_shift_end,
            second_shift_start=second_shift_start,second_shift_end=second_shift_end
            )
            #addition(request,user.doctor_information)
            user.doctor_information = doctor_information

        user.save()
        change(request, user, 'Changed fields.')
        return user, None
    else:
        if User.objects.filter(email=email).exists():
            return None, "A user with that email already exists."
        insurance = Insurance.objects.create(policy_number=policy,
            company=company)
        if not insurance:
            return None, "We could not create that user. Please try again."
        medical_information = MedicalInformation.objects.create(
            allergies=allergies, family_history=family_history,
            sex=sex, medications=medications,
            additional_info=additional_info, insurance=insurance,
            medical_conditions=medical_conditions
        )
        doctor_information = DoctorInformation.objects.create(specialisation=specialisation,
        years_of_experience=years_of_experience,fee=fee,degree=degree,visit_days=visit_days,
        two_shift=two_shift,first_shift_start=first_shift_start,first_shift_end=first_shift_end,
        second_shift_start=second_shift_start,second_shift_end=second_shift_end
        )
        user = User.objects.create_user(email, email=email,
            password=password, date_of_birth=date, phone_number=phone,
            first_name=first_name, last_name=last_name,
            medical_information=medical_information,doctor_information=doctor_information)
        if user is None:
            return None, "We could not create that user. Please try again."
        request.user = user
        addition(request, user)
        addition(request, medical_information)
        addition(request,doctor_information)
        addition(request, insurance)
        group.user_set.add(user)
        return user, None

def users(request):

    hospital = request.user.hospital()
    doctors = hospital.users_in_group('Doctor')
    patients = hospital.users_in_group('Patient')
    context = {
        'navbar': 'users',
        'doctors': doctors,
        'nurses': nurses,
        'patients': patients
    }
    return render(request, 'health/users.html', context)


def handle_appointment_form(request, body, user, appointment=None):
    """
    Validates the provided fields for an appointment request and creates one
    if all fields are valid.
    :param body: The HTTP form body containing the fields.
    :param user: The user intending to create the appointment.
    :return: A tuple containing either a valid appointment or failure message.
    """
    date_string = body.get("date")
    try:
        parsed = dateparse.parse_datetime(date_string)
        if not parsed:
            return None, "Invalid date or time."
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    except:
        return None, "Invalid date or time."
    duration = int(body.get("duration"))
    doctor_id = int(body.get("doctor", user.pk))
    doctor = User.objects.get(pk=doctor_id)
    patient_id = int(body.get("patient", user.pk))
    patient = User.objects.get(pk=patient_id)

    is_change = appointment is not None

    changed = []
    if is_change:
        if appointment.date != parsed:
            changed.append('date')
        if appointment.patient != patient:
            changed.append('patient')
        if appointment.duration != duration:
            changed.append('duration')
        if appointment.doctor != doctor:
            changed.append('doctor')
        appointment.delete()
    if not doctor.is_free(parsed, duration):
        return None, "The doctor is not free at that time." +\
                     " Please specify a different time."

    if not patient.is_free(parsed, duration):
        return None, "The patient is not free at that time." +\
                     " Please specify a different time."
    appointment = Appointment.objects.create(date=parsed, duration=duration,
                                             doctor=doctor, patient=patient)

    if is_change:
        change(request, appointment, changed)
    else:
        addition(request, appointment)
    if not appointment:
        return None, "We could not create the appointment. Please try again."
    return appointment, None

@login_required(login_url = "login")
def appointment_form(request, appointment_id):
    appointment = None
    if appointment_id:
        appointment = get_object_or_404(Appointment, pk=appointment_id)
    if request.POST:
        appointment, message = handle_appointment_form(
            request, request.POST,
            request.user, appointment=appointment
        )
        return schedule(request, error=message)
    hospital = request.user.hospital
    context = {
        "user": request.user,
        'appointment': appointment,
        #"doctors": hospital.users_in_group('Doctor'),
        #"patients": hospital.users_in_group('Patient')
        "doctors": User.objects.filter(groups__name='Doctor'),
        "patients": User.objects.filter(groups__name='Patient'),
    }
    return render(request, 'health/edit_appointment.html', context)

@login_required(login_url = "login")
def schedule(request, error=None):
    """
    Renders a page with an HTML form allowing the user to add an appointment
    with an existing doctor.
    Also shows a table of the existing appointments for the logged-in user.
    """
    now = timezone.now()
    hospital = request.user.hospital
    context = {
        "navbar": "schedule",
        "user": request.user,
        #"doctors": hospital.users_in_group('Doctor'),
        #"patients": hospital.users_in_group('Patient'),
        "doctors": User.objects.filter(groups__name='Doctor'),
        "patients": User.objects.filter(groups__name='Patient'),
        "schedule_future": request.user.schedule()
                                       .filter(date__gte=now)
                                       .order_by('date'),
        "schedule_past": request.user.schedule()
                                     .filter(date__lt=now)
                                     .order_by('-date')
    }
    if error:
        context['error_message'] = error
    return render(request, 'health/schedule.html', context)

@login_required(login_url = "login")
def add_appointment_form(request):
    return appointment_form(request, None)

@login_required(login_url = "login")
def delete_appointment(request, appointment_id):
    a = get_object_or_404(Appointment, pk=appointment_id)
    a.delete()
    return redirect(request,'health/schedule.html')


@login_required(login_url = '/login/')
def home(request):
    context = {
        'navbar': 'home',
        'user': request.user,
    }
    return render(request, 'health/home.html', context)
