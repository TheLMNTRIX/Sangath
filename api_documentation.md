# Sangath Healthcare API Documentation

## Base URL
The API base URL depends on your deployment environment.

## Authentication
The API uses Firebase Authentication. Most endpoints require a valid Bearer token in the Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

## Rate Limiting
No specific rate limiting is implemented, but standard Firebase quotas apply.

## User Roles
The API supports three user roles:
- Admin: Full system access and user management
- Supervisor: Patient management and ASHA oversight
- ASHA (Healthcare Worker): Patient interaction and session management

## Endpoints

### User Management

#### Check User Role
Check if a user exists and get their role.

**Endpoint**: `GET /check-role/{phone}`  
**Authentication**: Not required  
**URL Parameters**:
- `phone`: User's phone number with country code
**Response**:
```json
{
    "exists": true,
    "role": "ASHA"  // or "Supervisor", "Admin", "Unknown"
}
```

#### Register Supervisor
Create a new supervisor account (Admin only).

**Endpoint**: `POST /supervisors`  
**Authentication**: Required (Admin only)  
**Request Body**:
```json
{
    "phone": "+919876543210",  // Phone number with country code
    "name": "John Doe"
}
```
**Response**:
```json
{
    "phone": "+919876543210",
    "name": "John Doe",
    "role": "Supervisor",
    "profile_picture_url": null,
    "location": null,
    "district": null,
    "health_facility": null,
    "employee_id": null,
    "years_of_experience": null,
    "is_active": true,
    "created_at": "2024-01-07T12:00:00",
    "last_login": null,
    "profile_completed": false,
    "first_login": true
}
```

#### Register ASHA Worker
Create a new ASHA worker account (Supervisor or Admin only).

**Endpoint**: `POST /ashas`  
**Authentication**: Required (Supervisor or Admin)  
**Request Body**:
```json
{
    "phone": "+919876543210",
    "name": "Jane Doe",
    "district": "District Name",  // Optional
    "tehsil": "Tehsil Name"      // Optional
}
```
**Response**: Returns complete user object similar to supervisor registration.

#### Get All ASHA Workers
Retrieve a list of all ASHA workers.

**Endpoint**: `GET /allashas`  
**Authentication**: Required (Supervisor or Admin only)  
**Response**: Returns array of User objects
```json
[
    {
        "phone": "+919876543210",
        "name": "ASHA Name",
        "role": "ASHA",
        "district": "District Name",
        "profile_picture_url": "string?",
        "is_active": true,
        // ... other User model fields
    }
]
```

#### Update User Profile
Update a user's profile information.

**Endpoint**: `PUT /users/{phone}`  
**Authentication**: Required  
**URL Parameters**:
- `phone`: User's phone number with country code
**Request Body**:
```json
{
    "name": "Updated Name",
    "phone": "+919876543210",
    "profile_picture_url": "https://example.com/picture.jpg",
    "location": "City Name",
    "district": "District Name",
    "health_facility": "Facility Name",
    "employee_id": "EMP123",
    "years_of_experience": 5
}
```
**Notes**: 
- Users can only update their own profile unless they are Supervisor or Admin
- All fields are optional

#### Get User Profile
Retrieve a user's profile information.

**Endpoint**: `GET /users/{phone}`  
**Authentication**: Required  
**URL Parameters**:
- `phone`: User's phone number with country code
**Response**: Returns complete user object.

#### Delete User
Delete a user account and their Firebase Auth account (Admin only).

**Endpoint**: `DELETE /users/{phone}`  
**Authentication**: Required (Admin only)  
**URL Parameters**:
- `phone`: User's phone number with country code
**Response**:
```json
{
    "message": "User and authentication deleted successfully"
}
```

### Patient Management

#### Create Patient
Create a new patient record (Supervisor only).

**Endpoint**: `POST /patients`  
**Authentication**: Required (Supervisor only)  
**Request Body**:
```json
{
    "name": "Patient Name",
    "age": 25,
    "gender": "F",
    "district": "District Name",         // Optional
    "block_no": "123",                   // Optional
    "ward_no": "456",                    // Optional
    "rch_id": "RCH123",                 // Optional
    "pregnancy_state": "ANC",           // Optional, either "ANC" or "PNC"
    "high_risk": false,                 // Optional
    "high_risk_description": null,      // Required if high_risk is true
    "contact": "+919876543210",         // Optional
    "address": "Patient Address"        // Optional
}
```
**Response**: Returns created patient object with generated 8-digit patient_id.

#### Get All Patients
Retrieve all patients in the system.

**Endpoint**: `GET /allpatients`  
**Authentication**: Required (Supervisor or Admin only)  
**Response**: Returns array of patient objects with complete patient information.

#### Update Patient
Update patient information (Supervisor only).

**Endpoint**: `PUT /patients/{patient_id}`  
**Authentication**: Required (Supervisor only)  
**URL Parameters**:
- `patient_id`: Patient's unique ID
**Request Body**: Same fields as Create Patient (all optional)  
**Notes**:
- If `high_risk` is set to true, `high_risk_description` is required
- If `high_risk` is set to false, `high_risk_description` will be set to null
- Cannot modify patient_id, created_by, or created_at fields
**Response**:
```json
{
    "message": "Patient updated successfully",
    "data": {/* Updated patient object */}
}
```

#### Delete Patient
Delete a patient record (Supervisor only).

**Endpoint**: `DELETE /patients/{patient_id}`  
**Authentication**: Required (Supervisor only)  
**URL Parameters**:
- `patient_id`: Patient's unique ID
**Response**:
```json
{
    "message": "Patient deleted successfully"
}
```

#### Assign ASHA to Patient
Assign an ASHA worker to a patient (Supervisor only).

**Endpoint**: `PUT /patients/{patient_id}/assign`  
**Authentication**: Required (Supervisor only)  
**URL Parameters**:
- `patient_id`: Patient's unique ID
**Request Body**:
```json
{
    "asha_phone": "+919876543210"
}
```
**Response**:
```json
{
    "message": "ASHA assigned successfully"
}
```

#### Get ASHA's Patients
Retrieve all patients assigned to an ASHA worker.

**Endpoint**: `GET /ashas/{asha_phone}/patients`  
**Authentication**: Required  
**URL Parameters**:
- `asha_phone`: ASHA worker's phone number
**Notes**: 
- ASHA workers can only view their own patients
- Supervisors can view any ASHA's patients
**Response**: Returns array of patient objects.

#### Get Patient Details
Retrieve details for a specific patient.

**Endpoint**: `GET /patients/{patient_id}`  
**Authentication**: Required  
**URL Parameters**:
- `patient_id`: Patient's unique ID
**Response**: Returns complete patient object.

### Session Management

#### Create Session
Create a new session for a patient with optional audio recording.

**Endpoint**: `POST /patients/{patient_id}/sessions`  
**Authentication**: Required  
**URL Parameters**:
- `patient_id`: Patient's unique ID  
**Request Body**: Multipart form data with:
- `session_data`: JSON string containing:
```json
{
    "session_number": 1,        // Required, must be >= 1
    "notes": "Session notes",   // Optional
    "phq9_score": 10           // Optional, PHQ-9 depression screening score
}
```
- `audio_file`: Optional audio recording file
**Response**:
```json
{
    "id": "uuid-string",
    "patient_id": "string",
    "session_number": 1,
    "notes": "string?",
    "recording_url": "string?",
    "phq9_score": "number?",
    "asha_id": "string",
    "created_at": "datetime"
}
```

### Recording Management

#### Get ASHA's Recordings
Retrieve all recordings uploaded by an ASHA worker.

**Endpoint**: `GET /ashas/{asha_id}/recordings`  
**Authentication**: Required  
**URL Parameters**:
- `asha_id`: ASHA worker's phone number
**Response**: Returns array of Session objects with recordings
```json
[
    {
        "id": "uuid-string",
        "patient_id": "string",
        "session_number": 1,
        "notes": "string?",
        "recording_url": "string",
        "phq9_score": "number?",
        "asha_id": "string",
        "created_at": "datetime"
    }
]
```

#### Get Patient's Recordings
Retrieve all recordings for a specific patient.

**Endpoint**: `GET /patients/{patient_id}/recordings`  
**Authentication**: Required  
**URL Parameters**:
- `patient_id`: Patient's unique ID
**Response**: Returns array of Session objects with recordings (same format as ASHA's recordings)

## Error Responses
The API returns standard HTTP status codes along with error messages:

- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid or missing authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error

Example error response:
```json
{
    "detail": "Error message here"
}
```

## Data Models

### User Model
```json
{
    "phone": "string",           // Required, with country code
    "name": "string",           // Required
    "role": "string",           // Required: "ASHA" or "Supervisor"
    "profile_picture_url": "string?",
    "location": "string?",
    "district": "string?",
    "health_facility": "string?",
    "employee_id": "string?",
    "years_of_experience": "number?",
    "is_active": "boolean",
    "created_at": "datetime",
    "last_login": "datetime?",
    "profile_completed": "boolean",
    "first_login": "boolean"
}
```

### Patient Model
```json
{
    "patient_id": "string",     // Generated 8-digit ID
    "name": "string",          // Required
    "age": "number",          // Required
    "gender": "string",       // Required
    "district": "string?",
    "assigned_ashaid": "string?",
    "block_no": "string?",
    "ward_no": "string?",
    "rch_id": "string?",
    "pregnancy_state": "string?",  // "ANC" or "PNC"
    "high_risk": "boolean?",
    "high_risk_description": "string?",
    "contact": "string?",
    "address": "string?",
    "created_by": "string?",
    "created_at": "datetime"
}
```

### Session Model
```json
{
    "id": "string",              // UUID
    "patient_id": "string",      // Required
    "session_number": "number",  // Required, >= 1
    "notes": "string?",
    "recording_url": "string?",
    "phq9_score": "number?",
    "asha_id": "string",        // Set automatically from authenticated user
    "created_at": "datetime"    // Set automatically
}
```

## Important Notes for Frontend Implementation

1. **Authentication and Authorization**:
   - Maintain updated Firebase ID token
   - Include token in all authenticated requests
   - Handle token refresh appropriately
   - Implement role-based access control in UI
   - Store user role information securely

2. **File Upload Requirements**:
   - Audio recordings must use multipart/form-data
   - Session data must be stringified JSON
   - Handle large file uploads with proper progress indication
   - Implement retry mechanism for failed uploads

3. **Data Validation**:
   - Validate phone numbers include country code
   - Ensure session numbers are positive integers
   - Validate required vs optional fields
   - Handle high-risk patient requirements
   - Implement client-side validation matching server requirements

4. **Error Handling**:
   - Implement comprehensive error handling
   - Show appropriate user feedback for all error cases
   - Handle network errors gracefully
   - Implement proper loading states

5. **Patient Management**:
   - Handle 8-digit patient IDs properly
   - Maintain patient assignment workflow
   - Implement proper high-risk patient workflows
   - Preserve read-only fields during updates

6. **Session Management**:
   - Track session numbers sequentially
   - Handle audio file caching appropriately
   - Implement proper PHQ-9 score tracking
   - Manage session history effectively

7. **Performance Considerations**:
   - Implement proper pagination where needed
   - Cache appropriate data locally
   - Optimize audio file handling
   - Handle large lists efficiently