from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    phone: str
    name: str

class SupervisorCreate(UserBase):
    password: str
    role: str = "Supervisor"

class ASHACreate(UserBase):
    role: str = "ASHA"
    district: Optional[str] = None
    health_facility: Optional[str] = None

class UserLogin(BaseModel):
    identifier: str  # Can be email or phone
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    profile_picture_url: Optional[str] = None
    location: Optional[str] = None
    district: Optional[str] = None
    health_facility: Optional[str] = None
    employee_id: Optional[str] = None
    years_of_experience: Optional[int] = None

class User(BaseModel):
    # Authentication fields
    email: EmailStr
    phone: str
    
    # Basic info
    name: str
    role: str = Field(..., description="'ASHA' or 'Supervisor'")
    
    # Additional details
    profile_picture_url: Optional[str] = None
    location: Optional[str] = None
    
    # Professional details
    district: Optional[str] = None
    health_facility: Optional[str] = None
    employee_id: Optional[str] = None
    years_of_experience: Optional[int] = None
    
    # Account management
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    profile_completed: bool = False
    first_login: bool = True


class AudioRecording(BaseModel):
    filename: str
    asha_email: EmailStr
    supervisor_email: Optional[EmailStr] = None
    uploaded_at: datetime = datetime.utcnow()



__all__ = ["UserBase", "SupervisorCreate", "ASHACreate", "UserLogin", "UserUpdate", "User", "AudioRecording"]