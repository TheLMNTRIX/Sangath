from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal
from pydantic import ValidationError
import json
class UserBase(BaseModel):
    phone: str = Field(..., description="Phone number with country code (e.g., +911234567890)")
    name: str

class SupervisorCreate(UserBase):
    role: str = "Supervisor"

class ASHACreate(UserBase):
    role: str = "ASHA"
    district: Optional[str] = None
    tehsil: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    profile_picture_url: Optional[str] = None
    location: Optional[str] = None
    district: Optional[str] = None
    health_facility: Optional[str] = None
    employee_id: Optional[str] = None
    years_of_experience: Optional[int] = None

class User(BaseModel):
    phone: str
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
    asha_phone: str
    patient_id: str
    supervisor_phone: Optional[str] = None
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
    pregnancy_state: Optional[Literal["ANC", "PNC", "NA"]] = None

    high_risk: Optional[bool] = False
    high_risk_description: Optional[str] = None
    @field_validator('high_risk_description')
    def validate_high_risk_description(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get('high_risk') and not v:
            raise ValueError('Description is required when high risk is True')
        return v
    contact: Optional[str]
    address: Optional[str]
    patient_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)



class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    district: Optional[str] = None
    assigned_ashaid: Optional[str] = None
    block_no: Optional[str] = None
    ward_no: Optional[str] = None
    rch_id: Optional[str] = None
    pregnancy_state: Optional[Literal["ANC", "PNC"]] = None
    high_risk: Optional[bool] = None
    high_risk_description: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None

    @field_validator('high_risk_description')
    def validate_high_risk_description(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get('high_risk') and not v:
            raise ValueError('Description is required when high risk is True')
        return v
    

class SessionCreate(BaseModel):
    patient_id: str
    session_number: int = Field(..., ge=1)
    notes: Optional[str] = None
    recording_url: Optional[str] = None
    phq9_score: Optional[int] = None

class Session(SessionCreate):
    id: str
    asha_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

__all__ = ["UserBase", "SupervisorCreate", "ASHACreate", "UserLogin", "UserUpdate", "User", "AudioRecording", "PatientCreate", "PatientUpdate", "SessionCreate", "Session"]