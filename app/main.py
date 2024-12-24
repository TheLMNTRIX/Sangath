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
import logging
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio


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
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/time")
async def get_server_time():
    return JSONResponse({
        "server_time": int(datetime.utcnow().timestamp())
    })

@app.post("/login", response_model=dict)
async def login(form_data: UserLogin):
    """Login with phone number and password"""
    try:
        # Get user by phone number
        user = auth.get_user_by_phone_number(form_data.phone)
        
        # Get user data from Firestore
        user_doc = db.collection("users").document(user.uid).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Generate custom token
        custom_token = auth.create_custom_token(user.uid).decode('utf-8')
        
        # Exchange for ID token
        exchange_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}"
        payload = {"token": custom_token, "returnSecureToken": True}
        response = requests.post(exchange_url, json=payload)

        if response.status_code != 200:
            raise HTTPException(
                status_code=500, 
                detail="Failed to exchange custom token"
            )
        
        id_token = response.json().get("idToken")
        return {
            "access_token": id_token,
            "token_type": "bearer",
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {str(e)}"
        )

@app.post("/password-reset/request")
async def request_password_reset(reset_data: PasswordReset):
    """Request password reset using phone number"""
    try:
        # Verify phone number exists
        user = auth.get_user_by_phone_number(reset_data.phone)
        
        # Generate verification code
        verification_code = str(random.randint(100000, 999999))
        
        # Store verification code in Firestore with expiration
        db.collection("password_resets").document(user.uid).set({
            "code": verification_code,
            "expires_at": datetime.utcnow() + timedelta(minutes=15),
            "attempts": 0
        })
        
        # TODO: Send SMS with verification code using your SMS provider
        # For testing, just return the code (remove in production)
        return {"message": "Reset code sent", "code": verification_code}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number"
        )

@app.post("/password-reset/verify")
async def verify_reset_code(
    phone: str,
    code: str,
    new_password: str
):
    """Verify reset code and set new password"""
    try:
        # Get user by phone
        user = auth.get_user_by_phone_number(phone)
        
        # Get reset document
        reset_doc = db.collection("password_resets").document(user.uid).get()
        
        if not reset_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No reset code requested"
            )
            
        reset_data = reset_doc.to_dict()
        
        # Check expiration
        if datetime.fromisoformat(str(reset_data["expires_at"])) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code expired"
            )
            
        # Check attempts
        if reset_data["attempts"] >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many attempts"
            )
            
        # Verify code
        if reset_data["code"] != code:
            # Increment attempts
            db.collection("password_resets").document(user.uid).update({
                "attempts": reset_data["attempts"] + 1
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid code"
            )
            
        # Update password
        auth.update_user(user.uid, password=new_password)
        
        # Delete reset document
        db.collection("password_resets").document(user.uid).delete()
        
        return {"message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )



@app.post("/register/supervisor", status_code=status.HTTP_201_CREATED)
async def register_supervisor(user_data: SupervisorCreate):
    try:
        # Debug logging
        print(f"Attempting to register supervisor: {user_data.email}")
        
        # Check if user exists
        if db.collection("users").document(user_data.email).get().exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Verify Firebase API key is set
        if not FIREBASE_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase API key not configured"
            )
            
        try:
            # Create Firebase Auth user with more detailed error handling
            firebase_user = auth.create_user(
                email=user_data.email,
                password=user_data.password,
                phone_number=user_data.phone
            )
        except Exception as firebase_error:
            print(f"Firebase user creation failed: {str(firebase_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Firebase authentication error: {str(firebase_error)}"
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
        
        try:
            db.collection("users").document(user_data.email).set(user_doc)
        except Exception as db_error:
            print(f"Firestore operation failed: {str(db_error)}")
            # Clean up Firebase user if Firestore fails
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
    logger.info(f"Attempting to create ASHA with email: {asha_data.email}")
    
    # Verify supervisor role
    if current_user["role"] != "Supervisor":
        logger.error(f"Unauthorized attempt to create ASHA by {current_user['email']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Supervisors can create ASHA accounts"
        )    
    try:
        # Generate temporary password
        temp_password = "asha" + str(random.randint(10000, 99999))
        logger.debug(f"Generated temporary password for {asha_data.email}")
        
        # Create Firebase Auth user
        logger.info(f"Creating Firebase auth user for {asha_data.email}")
        firebase_user = auth.create_user(
            email=asha_data.email,
            password=temp_password,
            phone_number=asha_data.phone
        )
        
        logger.info(f"Firebase user created successfully with UID: {firebase_user.uid}")
        
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
        
        logger.info(f"Adding user document to Firestore for {asha_data.email}")
        db.collection("users").document(asha_data.email).set(user_doc)
        logger.info(f"Successfully created ASHA account for {asha_data.email}")
        
        return {"message": "ASHA created successfully", "temporary_password": temp_password}
    except Exception as e:
        logger.error(f"Error creating ASHA account: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating ASHA account: {str(e)}"
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
        
    # Return the user document data
    return user_doc.to_dict()
    

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
    # Add role check
    if current_user.get("role") != "Supervisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Supervisors can create patients"
        )
    patient_id = str(uuid.uuid4())

    patient_doc = {
        **patient.model_dump(),
        "id": patient_id,
        "created_at": datetime.utcnow(),
        "created_by": current_user["email"],
        "assigned_asha": None
    }
    
    db.collection("patients").document(patient_id).set(patient_doc)
    return {
        "message": "Patient created successfully",
        "id": patient_id  # Add this line to include ID in response
    }



@app.post("/patients/{patient_id}/assign-asha")
async def assign_asha_to_patient(
    patient_id: str,
    asha_email: EmailStr,
    current_user: dict = Depends(verify_user)
):
    logger.info(f"Attempting to assign ASHA {asha_email} to patient {patient_id}")
    
    if current_user["role"] != "Supervisor":
        logger.error(f"Unauthorized attempt to assign ASHA by {current_user['email']}")
        raise HTTPException(
            status_code=403,
            detail="Only Supervisors can assign ASHAs to patients"
        )
    
    # Verify ASHA exists
    logger.debug(f"Verifying ASHA existence: {asha_email}")
    asha_doc = db.collection("users").document(asha_email).get()
    if not asha_doc.exists or asha_doc.to_dict()["role"] != "ASHA":
        logger.error(f"ASHA not found or invalid role: {asha_email}")
        raise HTTPException(status_code=404, detail="ASHA not found")
    
    # Update patient document
    logger.debug(f"Updating patient {patient_id} with ASHA assignment")
    patient_ref = db.collection("patients").document(patient_id)
    patient_ref.update({
        "assigned_asha": asha_email,
        "last_updated": datetime.utcnow()
    })
    
    logger.info(f"Successfully assigned ASHA {asha_email} to patient {patient_id}")
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