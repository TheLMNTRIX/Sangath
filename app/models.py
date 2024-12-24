from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, Literal

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
    tehsil: Optional[str] = None

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
    patient_id: str
    supervisor_email: Optional[EmailStr] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    district: Optional[str] = None
    assigned_ashaid: Optional[str] = None
    block_no: Optional[str] = None
    ward_no: Optional[str] = None
    rch_id: Optional[str] = None
    pregnancy_state: Optional[Literal["ANC", "PNC"]] = None

    high_risk: Optional[bool] = False
    high_risk_description: Optional[str] = None
    @field_validator('high_risk_description')
    def validate_high_risk_description(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get('high_risk') and not v:
            raise ValueError('Description is required when high risk is True')
        return v
    
    contact: Optional[str]
    address: Optional[str]


__all__ = ["UserBase", "SupervisorCreate", "ASHACreate", "UserLogin", "UserUpdate", "User", "AudioRecording", "PatientCreate"]