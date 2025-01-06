
from fastapi import FastAPI, Depends, HTTPException, UploadFile, Form, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.config import db
from app.models import UserLogin, UserUpdate, SupervisorCreate, ASHACreate, AudioRecording, PatientCreate
from firebase_admin import auth, firestore
from datetime import datetime
from passlib.context import CryptContext
from typing import Optional
import random
import os
import requests
import logging
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
from pydantic import BaseModel

TEST_SUPERVISOR_PHONE = "+911234567891"
TEST_VERIFICATION_CODE = "123456"

class OTPRequest(BaseModel):
    phone: str

class LoginRequest(BaseModel):
    phone: str
    verification_code: str
    session_info: str


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
app = FastAPI(title="Sangath API")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
FIREBASE_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to verify Firebase ID token
async def verify_user(token: str = Depends(oauth2_scheme)):
    try:
        if token.startswith('Bearer '):
            token = token.split(' ')[1]
        
        print(f"Verifying token: {token[:50]}...")
        
        try:
            decoded_token = auth.verify_id_token(token)
        except Exception as e:
            print(f"Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}"
            )
        
        # Get user data from Firebase Auth
        user = auth.get_user(decoded_token['uid'])
        
        # Query by phone number
        user_doc = db.collection("users").document(user.phone_number).get()
        
        # If not found, query by UID to find ASHA document
        if not user_doc.exists:
            query = db.collection("users").where("uid", "==", user.uid).limit(1)
            docs = query.stream()
            user_docs = list(docs)
            
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
        print(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

@app.get("/time")
async def get_server_time():
    return JSONResponse({
        "server_time": int(datetime.utcnow().timestamp())
    })

# Update these endpoints in main.py

from pydantic import BaseModel

class OTPRequest(BaseModel):
    phone: str

class LoginRequest(BaseModel):
    phone: str
    verification_code: str
    session_info: str

@app.post("/auth/send-otp")
async def send_verification_code(request: OTPRequest):
    """
    Initiates phone verification by sending OTP via Firebase
    """
    try:
        # For test phone numbers, simulate OTP sending
        if request.phone == TEST_SUPERVISOR_PHONE:
            return {
                "session_info": "test-session-info",
                "message": "OTP sent successfully"
            }
            
        # Initialize verification (for non-test numbers)
        verification = auth.create_verification_session(
            phone_number=request.phone,
            recaptcha_token=None  # You'll need to implement reCAPTCHA in production
        )
        return {
            "session_info": verification.session_info,
            "message": "OTP sent successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send OTP: {str(e)}"
        )

@app.post("/login")
async def login(request: LoginRequest):
    """
    Verifies OTP and returns authentication token
    """
    try:
        # For test phone numbers, skip actual verification
        if request.phone == TEST_SUPERVISOR_PHONE and request.verification_code == "123456":
            try:
                user = auth.get_user_by_phone_number(request.phone)
            except auth.UserNotFoundError:
                user = auth.create_user(phone_number=request.phone)
                
            custom_token = auth.create_custom_token(user.uid).decode('utf-8')
            
            # Exchange for ID token
            exchange_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}"
            response = requests.post(exchange_url, json={
                "token": custom_token,
                "returnSecureToken": True
            })
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to exchange custom token for ID token"
                )
            
            id_token = response.json().get("idToken")
            return {
                "access_token": id_token,
                "token_type": "bearer"
            }
            
        # For non-test numbers, verify the OTP
        # Your production verification code here
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

@app.post("/register/supervisor", status_code=status.HTTP_201_CREATED)
async def register_supervisor(user_data: SupervisorCreate):
    try:
        print(f"Attempting to register supervisor: {user_data.phone}")
        
        # Check if user exists
        if db.collection("users").document(user_data.phone).get().exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
            
        try:
            firebase_user = auth.create_user(
                phone_number=user_data.phone,
                display_name=user_data.name
            )
        except Exception as firebase_error:
            print(f"Firebase user creation failed: {str(firebase_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Firebase authentication error: {str(firebase_error)}"
            )

        user_doc = {
            "phone": user_data.phone,
            "name": user_data.name,
            "role": "Supervisor",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "first_login": True,
            "profile_completed": False,
            "uid": firebase_user.uid
        }
        
        try:
            db.collection("users").document(user_data.phone).set(user_doc)
        except Exception as db_error:
            print(f"Firestore operation failed: {str(db_error)}")
            auth.delete_user(firebase_user.uid)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(db_error)}"
            )
            
        return {"message": "Supervisor registered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in register_supervisor: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/create/asha", status_code=status.HTTP_201_CREATED)
async def create_asha(asha_data: ASHACreate, current_user: dict = Depends(verify_user)):
    logger.info(f"Attempting to create ASHA with phone: {asha_data.phone}")
    
    if current_user["role"] != "Supervisor":
        logger.error(f"Unauthorized attempt to create ASHA by {current_user['phone']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Supervisors can create ASHA accounts"
        )    
    try:
        while True:
            asha_id = str(random.randint(100000, 999999))
            if not db.collection("users").document(asha_id).get().exists:
                break
        
        logger.info(f"Creating Firebase auth user for {asha_data.phone}")
        firebase_user = auth.create_user(
            phone_number=asha_data.phone,
            display_name=asha_data.name
        )
        
        logger.info(f"Firebase user created successfully with UID: {firebase_user.uid}")
        
        user_doc = {
            **asha_data.model_dump(),
            "asha_id": asha_id,
            "created_at": datetime.utcnow(),
            "is_active": True,
            "first_login": True,
            "profile_completed": False,
            "uid": firebase_user.uid,
            "supervisor_phone": current_user["phone"]
        }
        
        logger.info(f"Adding user document to Firestore for {asha_data.phone}")
        db.collection("users").document(asha_id).set(user_doc)
        logger.info(f"Successfully created ASHA account for {asha_data.phone}")
        
        return {
            "message": "ASHA created successfully",
            "asha_id": asha_id
        }
    except Exception as e:
        logger.error(f"Error creating ASHA account: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating ASHA account: {str(e)}"
        )

@app.put("/users/update")
async def update_user(
    update_data: UserUpdate,
    current_user: dict = Depends(verify_user)
):
    user_doc = db.collection("users").document(current_user["phone"])
    
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
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
    current_user: dict = Depends(verify_user)
):
    user_phone = current_user.get("phone")
    if not user_phone:
        raise HTTPException(status_code=400, detail="Phone not found in token")
    
    user_ref = db.collection("users").document(user_phone)
    user_ref.update({
        **profile_data,
        "profile_completed": True,
        "last_login": datetime.utcnow()
    })
    return {"message": "Profile updated successfully"}

@app.get("/users/profile")
async def get_profile(current_user: dict = Depends(verify_user)):
    user_phone = current_user.get("phone")
    if not user_phone:
        raise HTTPException(status_code=400, detail="Phone not found in token")
    
    user_doc = db.collection("users").document(user_phone).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user_doc.to_dict()

@app.post("/upload-audio/")
async def upload_audio(
    file: UploadFile, 
    asha_phone: str = Form(...), 
    current_user: dict = Depends(verify_user)
):
    user_doc = db.collection("users").document(current_user.get("phone")).get()
    if not user_doc.exists or user_doc.to_dict().get("role") != "ASHA":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only ASHAs can upload audio"
        )
    recording = AudioRecording(filename=file.filename, asha_phone=asha_phone)
    db.collection("audio_recordings").add(recording.dict())
    return {"message": "Audio uploaded successfully", "recording": recording.dict()}

@app.get("/audio-recordings/", response_model=list[AudioRecording])
async def list_audio_recordings(current_user: dict = Depends(verify_user)):
    if current_user.get("role") != "Supervisor":
        raise HTTPException(status_code=403, detail="Only Supervisors can access this endpoint.")
    recordings = db.collection("audio_recordings").stream()
    return [AudioRecording(**r.to_dict()) for r in recordings]

@app.post("/patients/create")
async def create_patient(
    patient: PatientCreate,
    current_user: dict = Depends(verify_user)
):
    logger.info(f"Attempting to create patient by user: {current_user['phone']}")
    
    if current_user["role"] != "Supervisor":
        logger.error(f"Unauthorized attempt to create patient by {current_user['phone']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Supervisors can create patients"
        )

    try:
        patient_id = str(uuid.uuid4())
        patient_doc = {
            **patient.model_dump(),
            "id": patient_id,
            "created_at": datetime.utcnow(),
            "created_by": current_user["phone"],
            "assigned_asha": None
        }
        
        db.collection("patients").document(patient_id).set(patient_doc)
        return {
            "message": "Patient created successfully",
            "id": patient_id
        }
    except Exception as e:
        logger.error(f"Error creating patient: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating patient: {str(e)}"
        )

@app.post("/patients/{patient_id}/assign-asha")
async def assign_asha_to_patient(
    patient_id: str,
    asha_id: str,
    current_user: dict = Depends(verify_user)
):
    logger.info(f"Attempting to assign ASHA {asha_id} to patient {patient_id}")
    
    if current_user["role"] != "Supervisor":
        logger.error(f"Unauthorized attempt to assign ASHA by {current_user['phone']}")
        raise HTTPException(
            status_code=403,
            detail="Only Supervisors can assign ASHAs to patients"
        )
    
    logger.debug(f"Verifying ASHA existence: {asha_id}")
    asha_doc = db.collection("users").document(asha_id).get()
    if not asha_doc.exists or asha_doc.to_dict()["role"] != "ASHA":
        logger.error(f"ASHA not found or invalid role: {asha_id}")
        raise HTTPException(status_code=404, detail="ASHA not found")
    
    logger.debug(f"Updating patient {patient_id} with ASHA assignment")
    patient_ref = db.collection("patients").document(patient_id)
    patient_ref.update({
        "assigned_asha": asha_id,
        "last_updated": datetime.utcnow()
    })
    
    logger.info(f"Successfully assigned ASHA {asha_id} to patient {patient_id}")
    return {"message": f"ASHA {asha_id} assigned to patient {patient_id}"}

@app.get("/patients/my-patients")
async def get_my_patients(current_user: dict = Depends(verify_user)):
    if current_user["role"] != "ASHA":
        raise HTTPException(
            status_code=403,
            detail="Only ASHAs can access their patient list"
        )
    
    # Get the current ASHA's document to find their asha_id
    asha_doc = db.collection("users").document(current_user["phone"]).get()
    if not asha_doc.exists:
        raise HTTPException(
            status_code=404,
            detail="ASHA user not found"
        )
    
    asha_id = asha_doc.to_dict().get("asha_id")
    
    # Query patients using the ASHA's ID
    patients = db.collection("patients")\
        .where("assigned_ashaid", "==", asha_id)\
        .stream()
    
    return [doc.to_dict() for doc in patients]