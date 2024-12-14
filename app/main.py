from fastapi import FastAPI, Depends, HTTPException, UploadFile, Form, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.config import db
from app.models import UserLogin, UserUpdate, SupervisorCreate, ASHACreate, AudioRecording, PatientCreate
from firebase_admin import auth, firestore
from pydantic import EmailStr
from datetime import datetime
from passlib.context import CryptContext
from typing import Optional
import random
import os
import requests

app = FastAPI(title="Sangath API")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
FIREBASE_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")



# Middleware to verify Firebase ID token
async def verify_user(token: str = Depends(oauth2_scheme)):
    try:
        # Strip 'Bearer ' if present
        if token.startswith('Bearer '):
            token = token.split(' ')[1]
        
        print(f"Verifying token: {token[:50]}...")  # Debug log
        
        try:
            # Try as ID token
            decoded_token = auth.verify_id_token(token)
        except Exception as e:
            print(f"Token: {token[:50]} Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token: {token[:50]} Token verification failed: {str(e)}"
            )
        
        # Get user data
        user = auth.get_user(decoded_token['uid'])
        user_doc = db.collection("users").document(user.email).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )
            
        return {
            "email": user.email,
            "uid": user.uid,
            "role": user_doc.to_dict().get("role")
        }
        
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@app.post("/login", response_model=dict)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Temporary login endpoint for Swagger UI testing only.
    Uses Firebase Admin to authenticate and provides an ID token for Swagger's OAuth2.
    """
    try:
        identifier = form_data.username
        if identifier.startswith("+"):
            user = auth.get_user_by_phone_number(identifier)
        else:
            user = auth.get_user_by_email(identifier)
        
        # Generate a Firebase custom token
        custom_token = auth.create_custom_token(user.uid).decode('utf-8')
        
        # Exchange custom token for an ID token (via Firebase REST API)
        exchange_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}"
        payload = {"token": custom_token, "returnSecureToken": True}
        response = requests.post(exchange_url, json=payload)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to exchange custom token for ID token")
        
        id_token = response.json().get("idToken")
        if not id_token:
            raise HTTPException(status_code=500, detail="ID token not found in response")
        
        # Return ID token for Swagger OAuth2
        return {
            "access_token": id_token,
            "token_type": "bearer",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {str(e)}"
        )




@app.post("/register/supervisor", status_code=status.HTTP_201_CREATED)
async def register_supervisor(user_data: SupervisorCreate):
    # Check if user exists
    if db.collection("users").document(user_data.email).get().exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    try:
        # Create Firebase Auth user
        firebase_user = auth.create_user(
            email=user_data.email,
            password=user_data.password,
            phone_number=user_data.phone
        )
        
        # Create User object for Firestore
        user_doc = {
            "email": user_data.email,
            "phone": user_data.phone,
            "name": user_data.name,
            "role": "Supervisor",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "first_login": True,
            "profile_completed": False,
            "uid": firebase_user.uid
        }
        
        db.collection("users").document(user_data.email).set(user_doc)
        return {"message": "Supervisor registered successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/create/asha", status_code=status.HTTP_201_CREATED)
async def create_asha(asha_data: ASHACreate, current_user: dict = Depends(verify_user)):
    # Verify supervisor role
    if current_user["role"] != "Supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Supervisors can create ASHA accounts"
        )    
    try:
        # Generate temporary password
        temp_password = "asha" + str(random.randint(10000, 99999))
        
        # Create Firebase Auth user
        firebase_user = auth.create_user(
            email=asha_data.email,
            password=temp_password,
            phone_number=asha_data.phone
        )
        
        # Create User object for Firestore
        user_doc = {
            **asha_data.model_dump(),
            "created_at": datetime.utcnow(),
            "is_active": True,
            "first_login": True,
            "profile_completed": False,
            "uid": firebase_user.uid,
            "supervisor_email": current_user["email"]
        }
        
        db.collection("users").document(asha_data.email).set(user_doc)
        return {"message": "ASHA created successfully", "temporary_password": temp_password}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.put("/users/update")
async def update_user(
    update_data: UserUpdate,
    token: str = Depends(verify_user)
):
    user = auth.verify_id_token(token)
    user_doc = db.collection("users").document(user["email"])
    
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Update password if provided
    if update_data.password:
        auth.update_user(user["uid"], password=update_data.password)
    
    # Update Firestore
    user_doc.update({
        **update_dict,
        "first_login": False,
        "profile_completed": True
    })
    
    return {"message": "Profile updated successfully"}

@app.put("/users/profile")
async def update_profile(
    profile_data: dict,
    token: str = Depends(verify_user)
):
    user_email = token.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="Email not found in token")
    
    user_ref = db.collection("users").document(user_email)
    user_ref.update({
        **profile_data,
        "profile_completed": True,
        "last_login": datetime.utcnow()
    })
    return {"message": "Profile updated successfully"}

@app.get("/users/profile")
async def get_profile(token: str = Depends(verify_user)):
    user_email = token.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="Email not found in token")
    
    user_doc = db.collection("users").document(user_email).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    

@app.post("/upload-audio/")
async def upload_audio(
    file: UploadFile, 
    asha_email: EmailStr = Form(...), 
    token: str = Depends(verify_user)
):
    user_doc = db.collection("users").document(token.get("email")).get()
    if not user_doc.exists or user_doc.to_dict().get("role") != "ASHA":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only ASHAs can upload audio"
        )
    recording = AudioRecording(filename=file.filename, asha_email=asha_email)
    db.collection("audio_recordings").add(recording.dict())
    return {"message": "Audio uploaded successfully", "recording": recording.dict()}

@app.get("/audio-recordings/", response_model=list[AudioRecording])
async def list_audio_recordings(token: str = Depends(verify_user)):
    user = auth.verify_id_token(token)
    if user.get("role") != "Supervisor":
        raise HTTPException(status_code=403, detail="Only Supervisors can access this endpoint.")
    recordings = db.collection("audio_recordings").stream()
    return [AudioRecording(**r.to_dict()) for r in recordings]

@app.post("/assign-asha/")
async def assign_asha(asha_email: EmailStr, supervisor_email: EmailStr, token: str = Depends(verify_user)):
    user = auth.verify_id_token(token)
    if user.get("role") != "Supervisor":
        raise HTTPException(status_code=403, detail="Only Supervisors can assign ASHAs.")
    # Logic for assignment can be implemented here (update Firestore with the relationship)
    return {"message": f"ASHA {asha_email} assigned to Supervisor {supervisor_email}."}


@app.post("/patients/create")
async def create_patient(
    patient: PatientCreate,
    current_user: dict = Depends(verify_user)
):
    if current_user["role"] != "Supervisor":
        raise HTTPException(
            status_code=403,
            detail="Only Supervisors can create patients"
        )
    
    patient_doc = {
        **patient.dict(),
        "created_at": datetime.utcnow(),
        "created_by": current_user["email"],
        "assigned_asha": None
    }
    
    db.collection("patients").add(patient_doc)
    return {"message": "Patient created successfully"}



@app.post("/patients/{patient_id}/assign-asha")
async def assign_asha_to_patient(
    patient_id: str,
    asha_email: EmailStr,
    current_user: dict = Depends(verify_user)
):
    if current_user["role"] != "Supervisor":
        raise HTTPException(
            status_code=403,
            detail="Only Supervisors can assign ASHAs to patients"
        )
    
    # Verify ASHA exists
    asha_doc = db.collection("users").document(asha_email).get()
    if not asha_doc.exists or asha_doc.to_dict()["role"] != "ASHA":
        raise HTTPException(status_code=404, detail="ASHA not found")
    
    # Update patient document
    patient_ref = db.collection("patients").document(patient_id)
    patient_ref.update({
        "assigned_asha": asha_email,
        "last_updated": datetime.utcnow()
    })
    
    return {"message": f"ASHA {asha_email} assigned to patient {patient_id}"}



@app.get("/patients/my-patients")
async def get_my_patients(current_user: dict = Depends(verify_user)):
    if current_user["role"] != "ASHA":
        raise HTTPException(
            status_code=403,
            detail="Only ASHAs can access their patient list"
        )
    
    patients = db.collection("patients")\
        .where("assigned_asha", "==", current_user["email"])\
        .stream()
    
    return [doc.to_dict() for doc in patients]