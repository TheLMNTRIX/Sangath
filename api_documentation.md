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
- Admin
- Supervisor
- ASHA (Healthcare Worker)

## Endpoints

### Server Time
Get the current server time.

**Endpoint**: `GET /time`  
**Authentication**: Not required  
**Response**:
```json
{
    "server_time": 1704200000  // Unix timestamp
}
```

### User Management

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
**Response**: Returns created patient object with generated patient_id.

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

### Recording Management

#### Upload Patient Recording
Upload an audio recording or text description for a patient session.

**Endpoint**: `POST /patients/{patient_id}/recordings`  
**Authentication**: Required  
**URL Parameters**:
- `patient_id`: Patient's unique ID
**Request Body**: 
- Multipart form data with:
  - `description`: Optional text description
  - `audio_file`: Optional audio file
**Notes**:
- At least one of description or audio_file must be provided
**Response**:
```json
{
    "message": "Recording uploaded successfully"
}
```

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

### Recording Model
```json
{
    "filename": "string",       // Required for audio uploads
    "asha_phone": "string",    // Required
    "patient_id": "string",    // Required
    "supervisor_phone": "string?",
    "uploaded_at": "datetime",
    "notes": "string?"
}
```