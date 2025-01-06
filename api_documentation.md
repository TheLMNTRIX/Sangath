# Sangath API Documentation

## Base URL
The API base URL depends on your deployment environment.

## Authentication
The API uses Firebase Authentication. Most endpoints require a valid Bearer token in the Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

## Rate Limiting
No specific rate limiting is implemented, but standard Firebase quotas apply.

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

### Authentication

#### Login
Authenticate a user and receive a Bearer token.

**Endpoint**: `POST /login`  
**Authentication**: Not required  
**Request Body**:
```json
{
    "username": "user@example.com",  // Email or phone number with + prefix
    "password": "password123"
}
```
**Response**:
```json
{
    "access_token": "firebase_id_token",
    "token_type": "bearer"
}
```

### User Management

#### Register Supervisor
Create a new supervisor account.

**Endpoint**: `POST /register/supervisor`  
**Authentication**: Not required  
**Request Body**:
```json
{
    "email": "supervisor@example.com",
    "phone": "+919876543210",
    "name": "John Doe",
    "password": "secure_password"
}
```
**Response**:
```json
{
    "message": "Supervisor registered successfully"
}
```

#### Create ASHA Worker
Create a new ASHA worker account.

**Endpoint**: `POST /create/asha`  
**Authentication**: Required (Supervisor only)  
**Request Body**:
```json
{
    "email": "asha@example.com",
    "phone": "+919876543210",
    "name": "Jane Doe",
    "district": "District Name",
    "tehsil": "Tehsil Name"
}
```
**Response**:
```json
{
    "message": "ASHA created successfully",
    "temporary_password": "asha12345",
    "asha_id": "123456"
}
```

#### Update User Profile
Update the current user's profile information.

**Endpoint**: `PUT /users/update`  
**Authentication**: Required  
**Request Body**:
```json
{
    "name": "Updated Name",
    "phone": "+919876543210",
    "password": "new_password",
    "profile_picture_url": "https://example.com/picture.jpg",
    "location": "City Name",
    "district": "District Name",
    "health_facility": "Facility Name",
    "employee_id": "EMP123",
    "years_of_experience": 5
}
```
**Response**:
```json
{
    "message": "Profile updated successfully"
}
```

#### Get User Profile
Retrieve the current user's profile information.

**Endpoint**: `GET /users/profile`  
**Authentication**: Required  
**Response**: Returns the complete user profile object.

### Patient Management

#### Create Patient
Create a new patient record.

**Endpoint**: `POST /patients/create`  
**Authentication**: Required (Supervisor only)  
**Request Body**:
```json
{
    "name": "Patient Name",
    "age": 25,
    "gender": "F",
    "district": "District Name",
    "block_no": "123",
    "ward_no": "456",
    "rch_id": "RCH123",
    "pregnancy_state": "ANC",
    "high_risk": false,
    "high_risk_description": null,
    "contact": "+919876543210",
    "address": "Patient Address"
}
```
**Response**:
```json
{
    "message": "Patient created successfully",
    "id": "uuid"
}
```

#### Assign ASHA to Patient
Assign an ASHA worker to a specific patient.

**Endpoint**: `POST /patients/{patient_id}/assign-asha`  
**Authentication**: Required (Supervisor only)  
**URL Parameters**:
- `patient_id`: UUID of the patient
**Request Body**:
```json
{
    "asha_id": "123456"
}
```
**Response**:
```json
{
    "message": "ASHA 123456 assigned to patient uuid"
}
```

#### Get ASHA's Patients
Retrieve all patients assigned to the current ASHA worker.

**Endpoint**: `GET /patients/my-patients`  
**Authentication**: Required (ASHA only)  
**Response**: Returns an array of patient objects assigned to the ASHA worker.

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