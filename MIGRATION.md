# Migration Guide: Flask to FastAPI

## Overview
This guide helps you migrate from the original Flask backend to the new FastAPI backend.

## Key Changes

### 1. Authentication
**Before (Flask)**: Session-based authentication with cookies
```javascript
// Sessions were handled automatically by the browser
fetch('/api/login', { credentials: 'include' })
```

**After (FastAPI)**: JWT token-based authentication
```javascript
// Tokens are stored in localStorage and sent in headers
const token = localStorage.getItem('capitalbay_token');
fetch('/api/login', { 
  headers: { 'Authorization': `Bearer ${token}` }
})
```

### 2. API Response Format
**Before**: Some endpoints returned different error formats
```json
{ "error": "Error message" }
```

**After**: Consistent FastAPI error format
```json
{ "detail": "Error message" }
```

### 3. Server Startup
**Before (Flask)**:
```bash
cd backend
python app.py
```

**After (FastAPI)**:
```bash
cd backend
python fastapi_app.py
# or for production:
python run_fastapi.py
```

### 4. API Documentation
**Before**: No automatic documentation

**After**: Automatic interactive documentation
- Swagger UI: http://127.0.0.1:5000/docs
- ReDoc: http://127.0.0.1:5000/redoc

## Frontend Changes

The frontend has been updated to work with JWT tokens. Key changes:

1. **Token Management**: Added localStorage-based token storage
2. **API Calls**: Updated to include Bearer tokens in headers
3. **Authentication Flow**: Modified login/logout to handle JWT tokens
4. **Error Handling**: Updated to handle FastAPI error format

## Database Schema
No changes to the database schema - the FastAPI backend uses the same SQLite database structure.

## Performance Improvements

1. **Async Operations**: All database operations are now asynchronous
2. **Better Concurrency**: Can handle multiple requests simultaneously
3. **Type Safety**: Full request/response validation with Pydantic
4. **Memory Efficiency**: Lower memory usage compared to Flask

## Backward Compatibility

The FastAPI backend maintains the same API endpoints as the Flask version:
- Same URL paths (`/api/startups`, `/api/login`, etc.)
- Same request/response data formats
- Same business logic and calculations

## Testing the Migration

1. **Start FastAPI server**: `python fastapi_app.py`
2. **Test basic endpoints**:
   ```bash
   curl http://127.0.0.1:5000/health
   curl http://127.0.0.1:5000/api/startups
   ```
3. **Test authentication**:
   ```bash
   # Register
   curl -X POST http://127.0.0.1:5000/api/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@test.com","password":"pass","name":"Test","user_type":"investor"}'
   
   # Login
   curl -X POST http://127.0.0.1:5000/api/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@test.com","password":"pass"}'
   ```

## Rollback Plan

If needed, you can rollback to Flask:
1. Stop FastAPI server
2. Start Flask server: `python app.py`
3. Revert frontend to use `script_flask_backup.js`

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure the frontend URL is in the FastAPI CORS configuration
2. **Token Expiry**: JWT tokens expire after 30 minutes by default
3. **Missing Dependencies**: Run `pip install -r requirements.txt` to install FastAPI dependencies

### Debug Mode
For development, enable debug mode in `fastapi_app.py`:
```python
uvicorn.run(app, host="127.0.0.1", port=5000, reload=True, log_level="debug")
```

## Next Steps

1. **Monitor Performance**: Compare response times and memory usage
2. **Update Documentation**: API docs are auto-generated at `/docs`
3. **Consider Upgrades**: PostgreSQL for production, Redis for caching
4. **Security Review**: Update JWT secret key for production