import os
import cv2
import pickle
import numpy as np
import mediapipe as mp
from django.urls import reverse
import qrcode
import base64
from io import BytesIO
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .models import CustomUser, PatientCondition, PatientMedication, PatientSurgery
from .management.commands.train_face_model import extract_embedding 
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
import json
from .models import (
    CustomUser, 
    DoctorProfile, 
    PatientProfile, 
    Gender, 
    BloodGroup,
    Condition, 
    Medication, 
    Surgery, 
    Allergy, 
    PatientCondition,
    PatientMedication,
    PatientSurgery
)


def register_view(request):
    if request.method == "GET":
        return render(request, "register.html")

    context = {"form_data": request.POST}
    
    try:
        role = request.POST.get("role")
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        gender_name = request.POST.get("gender")
        date_of_birth_str = request.POST.get("date_of_birth") 
        specialty = request.POST.get("specialty", "")

        if not all([role, first_name, last_name, email, password, gender_name, date_of_birth_str]):
            messages.error(request, "Խնդրում ենք լրացնել բոլոր պարտադիր դաշտերը։")
            return render(request, "register.html", context)
        
        if password != password2:
            messages.error(request, "Գաղտնաբառերը չեն համընկնում։")
            return render(request, "register.html", context)
            
        if len(password) < 8:
            messages.error(request, "Գաղտնաբառը պետք է բաղկացած լինի առնվազն 8 նիշից։")
            return render(request, "register.html", context)

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, f"'{email}' էլ․ հասցեով օգտատեր արդեն գոյություն ունի։")
            return render(request, "register.html", context)

        if role == 'doctor' and not specialty:
            messages.error(request, "Բժշկի համար անհրաժեշտ է նշել մասնագիտությունը։")
            return render(request, "register.html", context)

        with transaction.atomic():
            gender_obj, _ = Gender.objects.get_or_create(name=gender_name)

            user = CustomUser.objects.create_user(
                username=email, 
                email=email,
                password=password
            )

            user.first_name = first_name
            user.last_name = last_name
            user.date_of_birth = date_of_birth_str
            user.gender = gender_obj
            user.save()

            if role == 'doctor':
                DoctorProfile.objects.create(
                    user=user,
                    specialty=specialty,
                    license_number=f"TEMP-{user.id}"
                )
            else: 
                PatientProfile.objects.create(user=user)
        
        messages.success(request, "Դուք հաջողությամբ գրանցվել եք։ Այժմ կարող եք մուտք գործել։")
        return redirect("login")

    except IntegrityError as e:
        print("----------- INTEGRITY ERROR -----------")
        print(e)
        print("---------------------------------------")
        messages.error(request, "Գրանցման սխալ: Հնարավոր է՝ տվյալները կրկնվում են։")
        return render(request, "register.html", context)
        
    except ValidationError as e:
        print("----------- VALIDATION ERROR -----------")
        print(e.message_dict) 
        print("----------------------------------------")
        messages.error(request, f"Տվյալների սխալ։ Խնդրում ենք ստուգել լրացված դաշտերը։ {e.messages[0]}")
        return render(request, "register.html", context)
        
    except Exception as e:
        print("----------- GENERIC EXCEPTION -----------")
        print(f"EXCEPTION TYPE: {type(e).__name__}")
        print(f"EXCEPTION DETAILS: {e}")
        print("SUBMITTED DATA:", request.POST)
        print("---------------------------------------")
        messages.error(request, "Տեղի ունեցավ անսպասելի համակարգային սխալ։")
        return render(request, "register.html", context)

def login_page_view(request):
    return render(request, "login.html")


def login_api_view(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user = authenticate(
            request, username=data.get("email"), password=data.get("password")
        )
        if user:
            login(request, user)
            return JsonResponse({"status": "success", "redirect_url": "/profile/"})
        return JsonResponse(
            {"status": "error", "message": "Սխալ էլ. հասցե կամ գաղտնաբառ։"}, status=400
        )
    return JsonResponse({"status": "error", "message": "Invalid request."}, status=405)


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Դուք հաջողությամբ դուրս եկաք համակարգից։")
    return redirect('login')


@login_required
def profile_view(request):
    context = {}
    if hasattr(request.user, 'patient_profile'):
        patient_profile = request.user.patient_profile
        context['patient_conditions'] = PatientCondition.objects.filter(patient=patient_profile)
        context['patient_medications'] = PatientMedication.objects.filter(patient=patient_profile)
        context['patient_surgeries'] = PatientSurgery.objects.filter(patient=patient_profile)
    return render(request, "profile.html", context)


@login_required
def settings_view(request):
    user_to_update = request.user
    patient_profile = getattr(user_to_update, "patient_profile", None)
    doctor_profile = getattr(user_to_update, "doctor_profile", None)

    if request.method == "POST":
        try:
            with transaction.atomic():
                user_to_update.first_name = request.POST.get("first_name", user_to_update.first_name)
                user_to_update.last_name = request.POST.get("last_name", user_to_update.last_name)
                user_to_update.date_of_birth = request.POST.get("date_of_birth") or None
                user_to_update.gender_id = request.POST.get("gender") or None
                user_to_update.phone_number = request.POST.get("phone_number", user_to_update.phone_number)
                user_to_update.emergency_contact_phone = request.POST.get("emergency_contact_phone", user_to_update.emergency_contact_phone)
                user_to_update.address = request.POST.get("address", user_to_update.address)
                
                if "profile_picture" in request.FILES:
                    user_to_update.profile_picture = request.FILES["profile_picture"]
                user_to_update.save()

                if doctor_profile:
                    doctor_profile.specialty = request.POST.get("specialty", doctor_profile.specialty)
                    doctor_profile.license_number = request.POST.get("license_number", doctor_profile.license_number)
                    doctor_profile.workplace = request.POST.get("workplace", doctor_profile.workplace)
                    doctor_profile.biography = request.POST.get("biography", doctor_profile.biography)
                    doctor_profile.save()
                
                if patient_profile:
                    patient_profile.blood_group_id = request.POST.get("blood_group") or None
                    patient_profile.weight_kg = request.POST.get("weight_kg") or None
                    patient_profile.height_cm = request.POST.get("height_cm") or None
                    patient_profile.other_notes = request.POST.get("other_notes", patient_profile.other_notes)
                    patient_profile.save() 
                    allergies_text = request.POST.get("allergies_text", "")
                    allergy_names = [name.strip() for name in allergies_text.split(',') if name.strip()]
                    allergy_objs = []
                    for name in allergy_names:
                        obj, _ = Allergy.objects.get_or_create(name=name.capitalize())
                        allergy_objs.append(obj)
                    patient_profile.allergies.set(allergy_objs)

                    PatientCondition.objects.filter(patient=patient_profile).delete() 
                    conditions_text = request.POST.get("conditions_text", "")
                    condition_names = [name.strip() for name in conditions_text.split(',') if name.strip()]
                    for name in condition_names:
                        condition_obj, _ = Condition.objects.get_or_create(name=name.capitalize())
                        PatientCondition.objects.create(patient=patient_profile, condition=condition_obj)

                    PatientMedication.objects.filter(patient=patient_profile).delete() 
                    medications_text = request.POST.get("medications_text", "")
                    medication_names = [name.strip() for name in medications_text.split(',') if name.strip()]
                    for name in medication_names:
                        med_obj, _ = Medication.objects.get_or_create(name=name.capitalize())
                        PatientMedication.objects.create(patient=patient_profile, medication=med_obj)

                    PatientSurgery.objects.filter(patient=patient_profile).delete() 
                    surgeries_text = request.POST.get("surgeries_text", "")
                    surgery_names = [name.strip() for name in surgeries_text.split(',') if name.strip()]
                    for name in surgery_names:
                        surg_obj, _ = Surgery.objects.get_or_create(name=name.capitalize())
                        PatientSurgery.objects.create(patient=patient_profile, surgery=surg_obj)

            messages.success(request, "Ձեր տվյալները հաջողությամբ թարմացվել են։")
            return redirect("settings")
        
        except Exception as e:
            messages.error(request, f"Տվյալները պահպանելիս տեղի ունեցավ սխալ: {e}")

    context = {
        "all_genders": Gender.objects.all(),
        "all_blood_groups": BloodGroup.objects.all(),
    }
    if patient_profile:
        context.update({
            "p_allergies_str": ", ".join([a.name for a in patient_profile.allergies.all()]),
            "p_conditions_str": ", ".join([pc.condition.name for pc in PatientCondition.objects.filter(patient=patient_profile)]),
            "p_medications_str": ", ".join([pm.medication.name for pm in PatientMedication.objects.filter(patient=patient_profile)]),
            "p_surgeries_str": ", ".join([ps.surgery.name for ps in PatientSurgery.objects.filter(patient=patient_profile)]),
        })
    
    return render(request, "settings.html", context)    

def arvion(request):
    return render(request, "arvion.html")


def about_project(request):
    return render(request, "about_project.html")


def how_it_works(request):
    return render(request, "how_it_works.html")


def terms_privacy(request):
    return render(request, "terms_privacy.html")


def security(request):
    return render(request, "security.html")


def status(request):
    return render(request, "status.html")


@login_required
def qr_code_view(request):
    profile_url = request.build_absolute_uri(
        reverse('public_profile', args=[request.user.public_profile_id])
    )

    qr_image = qrcode.make(profile_url)
    
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    qr_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    data_uri = f"data:image/png;base64,{qr_image_base64}"

    context = {
        'qr_image_data_uri': data_uri,
        'profile_url': profile_url 
    }
    
    return render(request, 'qr_code.html', context)

def public_profile_view(request, profile_id):
    profile_user = get_object_or_404(CustomUser, public_profile_id=profile_id)
    
    context = {
        'profile_user': profile_user,
    }
    
    return render(request, 'public_profile.html', context)
def find_hospital(request):
    context = {
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'user': request.user 
    }
    return render(request, 'find_hospital.html', context)

def recognize_face(image_data):
    model_dir = os.path.join(settings.BASE_DIR, 'face_models')
    
    model_path = os.path.join(model_dir, "face_classifier.pkl")
    if not os.path.exists(model_path):
        return None, "Մոդելը դեռ մարզված չէ։"

    nparr = np.frombuffer(image_data.read(), np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    embedding = extract_embedding(image)
    if embedding is None:
        return None, "Նկարում դեմք չի հայտնաբերվել։"

    with open(model_path, "rb") as f:
        knn_clf = pickle.load(f)

    closest_distances = knn_clf.kneighbors([embedding], n_neighbors=1)
    
    distance_threshold = 1.2
    
    if closest_distances[0][0][0] <= distance_threshold:
        predicted_user_id = knn_clf.predict([embedding])[0]
        return predicted_user_id, "Ճանաչումը հաջողվեց։"
    else:
        return None, "Դեմքը չի ճանաչվել (համընկնում չի գտնվել բազայում)։"

@login_required
def search_patient_by_photo(request):
    if not hasattr(request.user, 'doctor_profile'):
        messages.error(request, "Այս էջը հասանելի է միայն բժիշկներին։")
        return redirect('profile')

    if request.method == 'POST':
        if 'patient_photo' not in request.FILES:
            messages.error(request, "Խնդրում ենք ընտրել ֆայլ։")
            return redirect('search_patient_by_photo')

        uploaded_file = request.FILES['patient_photo']
        
        user_id, message_text = recognize_face(uploaded_file)
        
        if user_id:
            return redirect('patient_details', user_id=user_id)
        else:
            messages.error(request, message_text)
            return redirect('search_patient_by_photo')

    return render(request, 'search_patient_by_photo.html')


@login_required
def patient_details_view(request, user_id):
    if not hasattr(request.user, 'doctor_profile'):
        messages.error(request, "Մուտքը սահմանափակված է։")
        return redirect('profile')

    patient_user = get_object_or_404(CustomUser, id=user_id, patient_profile__isnull=False)
    
    context = {
        'patient': patient_user,
        'patient_conditions': PatientCondition.objects.filter(patient=patient_user.patient_profile),
        'patient_medications': PatientMedication.objects.filter(patient=patient_user.patient_profile),
        'patient_surgeries': PatientSurgery.objects.filter(patient=patient_user.patient_profile),
    }
    return render(request, 'patient_details.html', context)