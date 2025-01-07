from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth, storage
from typing import Optional, List
import uuid
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import random
from pydantic import ValidationError
import json
from app.models import (
    SupervisorCreate, ASHACreate, UserUpdate, User, PatientCreate,
    AudioRecording, PatientUpdate, Session, SessionCreate
)
from app.config import db

app = FastAPI(title="Sangath Healthcare Application")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
bucket = storage.bucket('sangath-asha-test.firebasestorage.app')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only. In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def generate_patient_id():
    """Generate a unique 8-digit patient ID"""
    while True:
        # Generate a random 8-digit number
        patient_id = str(random.randint(10000000, 99999999))
        
        # Check if this ID already exists
        if not db.collection("patients").document(patient_id).get().exists:
            return patient_id

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
    
async def generate_recording_filename(patient_id: str, session_number: int, timestamp: datetime) -> str:
    """Generate unique filename for audio recording"""
    date_str = timestamp.strftime("%Y%m%d_%H%M%S")
    return f"audio-recordings/{patient_id}/session_{session_number}_{date_str}.mp3"

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

@app.get("/check-role/{phone}")
async def check_user_role(phone: str):
    """Check if user exists and return their role"""
    try:
        user_ref = db.collection("users").document(phone)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = user_doc.to_dict()
        return {
            "exists": True,
            "role": user_data.get("role", "Unknown")
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking user role: {str(e)}"
        )

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
    """Delete a user and their Firebase Auth account"""
    user_ref = db.collection("users").document(phone)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_data = user_doc.to_dict()
    
    try:
        # Delete Firebase Auth user
        auth.delete_user(user_data["uid"])
        
        # Remove ASHA assignments from patients if user is an ASHA
        if user_data["role"] == "ASHA":
            patients_ref = db.collection("patients").where("assigned_ashaid", "==", phone)
            for patient in patients_ref.stream():
                patient.reference.update({"assigned_ashaid": None})
        
        # Delete Firestore user document
        user_ref.delete()
        
        return {"message": "User and authentication deleted successfully"}
        
    except Exception as firebase_error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(firebase_error)}"
        )

@app.post("/patients", response_model=PatientCreate)
async def create_patient(
    patient: PatientCreate,
    current_user: dict = Depends(verify_supervisor)
):
    
    user_doc = db.collection("users").document(current_user["doc_id"]).get()
    user_data = user_doc.to_dict()
    creator_name = user_data.get("name", "Unknown User")

    """Create a new patient with 8-digit ID"""
    # Generate unique 8-digit patient ID
    patient_id = await generate_patient_id()
    
    patient_ref = db.collection("patients").document(patient_id)
    
    patient_data = patient.model_dump()
    patient_data.update({
        "created_at": datetime.utcnow(),
        "created_by": creator_name,
        "patient_id": patient_id  # Store the ID in the document as well
    })
    
    patient_ref.set(patient_data)
    return PatientCreate(**patient_data)

@app.put("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,  # Use PatientUpdate instead of PatientCreate
    current_user: dict = Depends(verify_supervisor)
):
    """Update patient details"""
    patient_ref = db.collection("patients").document(patient_id)
    patient_doc = patient_ref.get()
    
    if not patient_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Get current patient data
    current_data = patient_doc.to_dict()
    
    # Get only the fields that were provided in the update
    update_data = {
        k: v for k, v in patient_update.model_dump().items()
        if v is not None  # Only include fields that were explicitly set
    }
    
    # Special handling for high_risk and high_risk_description
    if 'high_risk' in update_data:
        if update_data['high_risk']:
            if not update_data.get('high_risk_description') and not current_data.get('high_risk_description'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Description is required when high risk is True"
                )
        else:
            # If high_risk is set to False, remove the description
            update_data['high_risk_description'] = None
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid update data provided"
        )
    
    # Preserve read-only fields
    update_data.pop('patient_id', None)
    update_data.pop('created_by', None)
    update_data.pop('created_at', None)
    
    # Update the document
    patient_ref.update(update_data)
    
    # Return updated patient data
    updated_doc = patient_ref.get()
    return {"message": "Patient updated successfully", "data": updated_doc.to_dict()}

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
    print(f"Attempting to assign ASHA. Phone: {asha_phone}, Patient ID: {patient_id}")
    
    # Verify ASHA exists
    asha_ref = db.collection("users").document(asha_phone)
    asha_doc = asha_ref.get()
    
    print(f"ASHA document exists: {asha_doc.exists}")
    if asha_doc.exists:
        asha_data = asha_doc.to_dict()
        print(f"ASHA document data: {asha_data}")
        print(f"ASHA role: {asha_data.get('role')}")
    
    if not asha_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ASHA with phone {asha_phone} not found"
        )
    
    asha_data = asha_doc.to_dict()
    if asha_data["role"] != "ASHA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with phone {asha_phone} is not an ASHA worker"
        )
    
    # Update patient
    patient_ref = db.collection("patients").document(patient_id)
    patient_doc = patient_ref.get()
    
    print(f"Patient document exists: {patient_doc.exists}")
    
    if not patient_doc.exists:
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

@app.get("/allashas", response_model=List[User])
async def get_all_ashas(current_user: dict = Depends(verify_supervisor_or_admin)):
    """Get all ASHA workers (Admin and Supervisor only)"""
    try:
        users_ref = db.collection("users").where("role", "==", "ASHA")
        ashas = [User(**doc.to_dict()) for doc in users_ref.stream()]
        return ashas
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching ASHA workers: {str(e)}"
        )
    

@app.get("/allpatients")
async def get_all_patients(current_user: dict = Depends(verify_supervisor_or_admin)):
    """Get all patients (Admin and Supervisor only)"""
    try:
        patients_ref = db.collection("patients")
        patients = [doc.to_dict() for doc in patients_ref.stream()]
        return patients
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching patients: {str(e)}"
        )


@app.get("/patients/{patient_id}")
async def get_patient(
    patient_id: str,
    current_user: dict = Depends(verify_user)
):
    """Get patient details by ID"""
    patient_ref = db.collection("patients").document(patient_id)
    patient_doc = patient_ref.get()
    
    if not patient_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return patient_doc.to_dict()

@app.post("/patients/{patient_id}/sessions", response_model=Session)
async def create_session(
    patient_id: str,
    session_data: str = Form(...),  # Change this to accept string
    audio_file: Optional[UploadFile] = File(default=None),
    current_user: dict = Depends(verify_user)
):
    """Create a new session with optional audio recording"""
    
    try:
        # Parse the session_data JSON string into a SessionCreate model
        session_data_dict = json.loads(session_data)
        session_model = SessionCreate(**session_data_dict)
        
        # Verify patient exists
        patient_ref = db.collection("patients").document(patient_id)
        if not patient_ref.get().exists:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        # Create session document
        session_data_dict = session_model.model_dump()
        session_data_dict["asha_id"] = current_user["phone"]
        session_id = str(uuid.uuid4())
        
        if audio_file:
            # Upload audio to Firebase Storage
            timestamp = datetime.utcnow()
            filename = await generate_recording_filename(patient_id, session_model.session_number, timestamp)
            blob = bucket.blob(filename)
            
            # Read and upload file
            content = await audio_file.read()
            blob.upload_from_string(content, content_type=audio_file.content_type)
            
            # Generate public URL
            blob.make_public()
            session_data_dict["recording_url"] = blob.public_url
        
        # Add creation timestamp
        session_data_dict["created_at"] = datetime.utcnow()
        
        # Store session in Firestore
        session_ref = db.collection("sessions").document(session_id)
        session_ref.set(session_data_dict)
        
        return Session(id=session_id, **session_data_dict)
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Invalid JSON format in session_data"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )
    

@app.get("/ashas/{asha_id}/recordings", response_model=List[Session])
async def get_asha_recordings(
    asha_id: str,
    current_user: dict = Depends(verify_user)
):
    """Get all recordings uploaded by an ASHA"""
        
    # First get all sessions by this ASHA
    sessions = db.collection("sessions")\
        .where("asha_id", "==", asha_id)\
        .stream()
    
    # Filter for sessions with recordings in Python
    recordings = [
        Session(id=session.id, **session.to_dict())
        for session in sessions
        if session.to_dict().get("recording_url") is not None
    ]
        
    return recordings

@app.get("/patients/{patient_id}/recordings", response_model=List[Session])
async def get_patient_recordings(
    patient_id: str,
    current_user: dict = Depends(verify_user)
):
    """Get all recordings for a specific patient"""
    # Verify patient exists
    patient_ref = db.collection("patients").document(patient_id)
    if not patient_ref.get().exists:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    sessions = db.collection("sessions")\
        .where("patient_id", "==", patient_id)\
        .stream()
    
   
    recordings = [
        Session(id=session.id, **session.to_dict())
        for session in sessions
        if session.to_dict().get("recording_url") is not None
    ]
        
    return recordings