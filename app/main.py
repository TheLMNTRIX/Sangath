from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from typing import Optional, List
import uuid
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    SupervisorCreate, ASHACreate, UserUpdate, User, PatientCreate,
    AudioRecording
)
from app.config import db

app = FastAPI(title="Sangath Healthcare Application")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only. In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Verify user function as provided
async def verify_user(token: str = Depends(oauth2_scheme)):
    try:
        if token.startswith('Bearer '):
            token = token.split(' ')[1]
        
        try:
            decoded_token = auth.verify_id_token(token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}"
            )
        
        user = auth.get_user(decoded_token['uid'])
        user_doc = db.collection("users").document(user.phone_number).get()
        
        if not user_doc.exists:
            query = db.collection("users").where("uid", "==", user.uid).limit(1)
            user_docs = list(query.stream())
            
            if not user_docs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found in database"
                )
            user_doc = user_docs[0]
            
        user_data = user_doc.to_dict()
        return {
            "phone": user.phone_number,
            "uid": user.uid,
            "role": user_data.get("role"),
            "doc_id": user_doc.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

# Helper function to check if user is supervisor
async def verify_supervisor(current_user = Depends(verify_user)):
    if current_user["role"] != "Supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors can perform this action"
        )
    return current_user

async def verify_admin(current_user = Depends(verify_user)):
    if current_user["role"] != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    return current_user

# Helper function to check if user is supervisor or admin
async def verify_supervisor_or_admin(current_user = Depends(verify_user)):
    if current_user["role"] not in ["Supervisor", "Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors or administrators can perform this action"
        )
    return current_user

@app.post("/supervisors", response_model=User)
async def register_supervisor(
    supervisor: SupervisorCreate,
    current_user: dict = Depends(verify_admin)
):
    """Register a new supervisor (Admin only)"""
    # Check if user already exists in Firestore
    user_ref = db.collection("users").document(supervisor.phone)
    if user_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    try:
        # Create Firebase Auth user
        firebase_user = auth.create_user(
            phone_number=supervisor.phone,
            display_name=supervisor.name
        )
        
        user_data = {
            **supervisor.model_dump(),
            "created_at": datetime.utcnow(),
            "is_active": True,
            "profile_completed": False,
            "first_login": True,
            "uid": firebase_user.uid
        }
        
        # Create Firestore user document
        user_ref.set(user_data)
        return User(**user_data)
        
    except Exception as firebase_error:
        print(f"Firebase user creation failed: {str(firebase_error)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Firebase authentication error: {str(firebase_error)}"
        )

@app.post("/ashas", response_model=User)
async def register_asha(
    asha: ASHACreate,
    current_user: dict = Depends(verify_supervisor_or_admin)
):
    """Register a new ASHA worker (Supervisor or Admin)"""
    # Check if user already exists in Firestore
    user_ref = db.collection("users").document(asha.phone)
    if user_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    try:
        # Create Firebase Auth user
        firebase_user = auth.create_user(
            phone_number=asha.phone,
            display_name=asha.name
        )
        
        user_data = {
            **asha.model_dump(),
            "created_at": datetime.utcnow(),
            "is_active": True,
            "profile_completed": False,
            "first_login": True,
            "uid": firebase_user.uid,
            "created_by": current_user["phone"]
        }
        
        # Create Firestore user document
        user_ref.set(user_data)
        return User(**user_data)
        
    except Exception as firebase_error:
        print(f"Firebase user creation failed: {str(firebase_error)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Firebase authentication error: {str(firebase_error)}"
        )

@app.put("/users/{phone}", response_model=User)
async def update_user(
    phone: str,
    user_update: UserUpdate,
    current_user: dict = Depends(verify_user)
):
    """Update user profile"""
    if current_user["phone"] != phone and current_user["role"] not in ["Supervisor", "Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update own profile unless supervisor or admin"
        )
    
    user_ref = db.collection("users").document(phone)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
    user_ref.update(update_data)
    
    updated_doc = user_ref.get()
    return User(**updated_doc.to_dict())

@app.get("/users/{phone}", response_model=User)
async def get_user_profile(
    phone: str,
    current_user: dict = Depends(verify_user)
):
    """Fetch user profile"""
    user_ref = db.collection("users").document(phone)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return User(**user_doc.to_dict())

@app.delete("/users/{phone}")
async def delete_user(
    phone: str,
    current_user: dict = Depends(verify_admin)
):
    """Delete a user"""
    user_ref = db.collection("users").document(phone)
    if not user_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Remove ASHA assignments from patients
    if user_ref.get().to_dict()["role"] == "ASHA":
        patients_ref = db.collection("patients").where("assigned_ashaid", "==", phone)
        for patient in patients_ref.stream():
            patient.reference.update({"assigned_ashaid": None})
    
    user_ref.delete()
    return {"message": "User deleted successfully"}

@app.post("/patients", response_model=PatientCreate)
async def create_patient(
    patient: PatientCreate,
    current_user: dict = Depends(verify_user)
):
    """Create a new patient"""
    patient_id = str(uuid.uuid4())
    patient_ref = db.collection("patients").document(patient_id)
    
    patient_data = patient.model_dump()
    patient_data["created_at"] = datetime.utcnow()
    patient_data["created_by"] = current_user["phone"]
    
    patient_ref.set(patient_data)
    return PatientCreate(**patient_data)

@app.put("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    patient_update: PatientCreate,
    current_user: dict = Depends(verify_user)
):
    """Update patient details"""
    patient_ref = db.collection("patients").document(patient_id)
    if not patient_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    update_data = patient_update.model_dump(exclude_unset=True)
    patient_ref.update(update_data)
    
    return {"message": "Patient updated successfully"}

@app.delete("/patients/{patient_id}")
async def delete_patient(
    patient_id: str,
    current_user: dict = Depends(verify_supervisor)
):
    """Delete a patient"""
    patient_ref = db.collection("patients").document(patient_id)
    if not patient_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    patient_ref.delete()
    return {"message": "Patient deleted successfully"}

@app.put("/patients/{patient_id}/assign")
async def assign_asha(
    patient_id: str,
    asha_phone: str,
    current_user: dict = Depends(verify_supervisor)
):
    """Assign an ASHA to a patient"""
    # Verify ASHA exists
    asha_ref = db.collection("users").document(asha_phone)
    asha_doc = asha_ref.get()
    
    if not asha_doc.exists or asha_doc.to_dict()["role"] != "ASHA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ASHA worker"
        )
    
    # Update patient
    patient_ref = db.collection("patients").document(patient_id)
    if not patient_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    patient_ref.update({"assigned_ashaid": asha_phone})
    return {"message": "ASHA assigned successfully"}

@app.get("/ashas/{asha_phone}/patients")
async def get_asha_patients(
    asha_phone: str,
    current_user: dict = Depends(verify_user)
):
    """Get all patients assigned to an ASHA"""
    if current_user["phone"] != asha_phone and current_user["role"] != "Supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view own patients unless supervisor"
        )
    
    patients_ref = db.collection("patients").where("assigned_ashaid", "==", asha_phone)
    patients = [doc.to_dict() for doc in patients_ref.stream()]
    return patients

@app.post("/patients/{patient_id}/recordings")
async def upload_recording(
    patient_id: str,
    description: str = Form(None),
    audio_file: UploadFile = File(None),
    current_user: dict = Depends(verify_user)
):
    """Upload an audio recording or text description for a patient session"""
    if not audio_file and not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either audio file or description is required"
        )
    
    patient_ref = db.collection("patients").document(patient_id)
    if not patient_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    recording_data = {
        "patient_id": patient_id,
        "asha_phone": current_user["phone"],
        "uploaded_at": datetime.utcnow(),
        "notes": description
    }
    
    if audio_file:
        # Here you would typically upload the file to storage
        # and store the URL in recording_data["filename"]
        recording_data["filename"] = f"recordings/{patient_id}/{uuid.uuid4()}"
    
    recording_ref = db.collection("recordings").document()
    recording_ref.set(recording_data)
    
    return {"message": "Recording uploaded successfully"}