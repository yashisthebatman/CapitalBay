"""
FastAPI backend for CapitalBay - High-performance async rewrite
"""

import os
import json
import datetime
from typing import List, Optional, Dict, Any
import asyncio
import aiosqlite
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
import logging

# Configuration
DATABASE = 'database.db'
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()

# Pydantic Models
class UserBase(BaseModel):
    email: str
    name: str
    user_type: str
    
    @classmethod
    def validate_user_type(cls, v):
        if v not in ['startup', 'investor']:
            raise ValueError('user_type must be startup or investor')
        return v

class UserRegister(UserBase):
    password: str
    # Optional startup fields
    company_name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    funding_goal: Optional[float] = 0
    funding_acquired: Optional[float] = 0
    years_operating: Optional[int] = 0
    website: Optional[str] = None
    logo_url: Optional[str] = None
    contact_phone: Optional[str] = None
    equity_offered: Optional[float] = 0
    financials: Optional[List[Dict[str, Any]]] = []

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserInfo(BaseModel):
    id: int
    email: str
    name: str
    user_type: str

class FinancialRecord(BaseModel):
    year: int
    revenue: Optional[float] = None
    profit: Optional[float] = None

class StartupCard(BaseModel):
    id: int
    company_name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    funding_goal: Optional[float] = None
    funding_acquired: Optional[float] = None
    logo_url: Optional[str] = None
    risk_category: str

class StartupDetail(BaseModel):
    id: int
    company_name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    funding_goal: Optional[float] = None
    funding_acquired: Optional[float] = None
    years_operating: Optional[int] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    contact_phone: Optional[str] = None
    equity_offered: Optional[float] = None
    financial_history: List[FinancialRecord] = []
    founder_name: str
    founder_email: str
    risk_analysis: Dict[str, Any]
    calculated_valuation: Optional[float] = None
    investor_has_expressed_interest: bool = False

class StartupUpdate(BaseModel):
    company_name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    funding_goal: Optional[float] = None
    funding_acquired: Optional[float] = None
    years_operating: Optional[int] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    contact_phone: Optional[str] = None
    equity_offered: Optional[float] = None

class Analytics(BaseModel):
    interested_investors: List[Dict[str, str]]

# Database connection manager
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def get_connection(self):
        return await aiosqlite.connect(self.db_path)
    
    async def init_db(self):
        """Initialize database with tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DROP TABLE IF EXISTS investor_interest")
            await db.execute("DROP TABLE IF EXISTS startups")
            await db.execute("DROP TABLE IF EXISTS users")
            
            # Users table
            await db.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    user_type TEXT NOT NULL CHECK(user_type IN ('startup', 'investor')),
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Startups table
            await db.execute('''
                CREATE TABLE startups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    company_name TEXT NOT NULL,
                    description TEXT,
                    industry TEXT,
                    funding_goal REAL DEFAULT 0,
                    funding_acquired REAL DEFAULT 0,
                    years_operating INTEGER DEFAULT 0,
                    website TEXT,
                    logo_url TEXT,
                    financial_history TEXT,
                    contact_phone TEXT,
                    equity_offered REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            # Investor interest table
            await db.execute('''
                CREATE TABLE investor_interest (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investor_user_id INTEGER NOT NULL,
                    startup_id INTEGER NOT NULL,
                    expressed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(investor_user_id, startup_id),
                    FOREIGN KEY (investor_user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (startup_id) REFERENCES startups (id) ON DELETE CASCADE
                )
            ''')
            
            await db.commit()
            logger.info("Database initialized successfully")

# Global database manager
db_manager = DatabaseManager(DATABASE)

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not os.path.exists(DATABASE):
        logger.info(f"Database file '{DATABASE}' not found. Initializing...")
        await db_manager.init_db()
    yield
    # Shutdown
    pass

# FastAPI app
app = FastAPI(
    title="CapitalBay API",
    description="Connecting Innovators and Investors",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://127.0.0.1:5500", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Get current user without raising an error if not authenticated"""
    if not credentials:
        return None
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    
    if user is None:
        return None
    
    return {
        "id": user[0],
        "email": user[1],
        "user_type": user[3],
        "name": user[4]
    }

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user with authentication required"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    
    if user is None:
        raise credentials_exception
    
    return {
        "id": user[0],
        "email": user[1],
        "user_type": user[3],
        "name": user[4]
    }

def calculate_risk(startup_data: dict) -> dict:
    """Calculate simplified risk score and category"""
    risk_score = 0
    reasons = []
    
    goal = startup_data.get('funding_goal', 0) or 0
    acquired = startup_data.get('funding_acquired', 0) or 0
    years = startup_data.get('years_operating', 0) or 0
    financials = startup_data.get('financial_history', [])
    
    if not isinstance(financials, list):
        financials = []
    
    # Factor 1: Funding Gap
    if goal > 0 and acquired < (goal * 0.25):
        risk_score += 2
        reasons.append("Significant funding gap remaining.")
    elif goal > 0 and acquired < (goal * 0.75):
        risk_score += 1
        reasons.append("Moderate funding gap remaining.")
    
    # Factor 2: Operating History
    if years < 1:
        risk_score += 2
        reasons.append("Very early stage (less than 1 year operating).")
    elif years < 3:
        risk_score += 1
        reasons.append("Relatively early stage (1-3 years operating).")
    
    # Factor 3: Financial Health
    if financials:
        try:
            last_year_data = financials[-1]
            revenue = last_year_data.get('revenue')
            profit = last_year_data.get('profit')
            
            if profit is not None and profit <= 0:
                risk_score += 1
                reasons.append("Last reported year shows no profit or a loss.")
            elif revenue is not None and revenue < 10000:
                risk_score += 1
                reasons.append("Last reported year shows very low revenue.")
            elif profit is not None and profit > 0:
                risk_score -= 0.5
        except (IndexError, TypeError, ValueError):
            pass
    else:
        risk_score += 1
        reasons.append("No detailed financial history provided.")
    
    # Factor 4: Large Funding Goal
    if goal > 1000000:
        risk_score += 1
        reasons.append("Seeking significant funding amount (>$1M).")
    
    risk_score = max(0, risk_score)
    
    # Determine Category
    if risk_score >= 4:
        category = "High Risk"
    elif risk_score >= 2:
        category = "Average Risk"
    else:
        category = "Low Risk"
    
    return {"score": round(risk_score, 1), "category": category, "reasons": reasons}

def calculate_valuation(startup_data: dict) -> Optional[float]:
    """Calculate simplified estimated valuation"""
    try:
        goal = float(startup_data.get('funding_goal', 0) or 0)
        equity = float(startup_data.get('equity_offered', 0) or 0)
        
        if equity > 0 and equity <= 100 and goal > 0:
            post_money_valuation = goal / (equity / 100.0)
            pre_money_valuation = post_money_valuation - goal
            return max(0, round(pre_money_valuation))
        else:
            return None
    except (ValueError, TypeError, ZeroDivisionError):
        return None

# API Routes

@app.post("/api/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    async with aiosqlite.connect(DATABASE) as db:
        # Check if email exists
        async with db.execute("SELECT id FROM users WHERE email = ?", (user_data.email,)) as cursor:
            existing_user = await cursor.fetchone()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Insert user
        async with db.execute(
            "INSERT INTO users (email, password_hash, user_type, name) VALUES (?, ?, ?, ?)",
            (user_data.email, hashed_password, user_data.user_type, user_data.name)
        ) as cursor:
            user_id = cursor.lastrowid
        
        # If startup, create startup profile
        if user_data.user_type == 'startup':
            company_name = user_data.company_name or user_data.name
            
            # Process financial history
            financial_history_json = None
            if user_data.financials:
                validated_financials = []
                for item in user_data.financials:
                    if isinstance(item, dict) and 'year' in item:
                        try:
                            validated_item = {
                                'year': int(item['year']),
                                'revenue': float(item.get('revenue')) if item.get('revenue') is not None else None,
                                'profit': float(item.get('profit')) if item.get('profit') is not None else None
                            }
                            validated_financials.append(validated_item)
                        except (ValueError, TypeError):
                            logger.warning(f"Skipping invalid financial entry: {item}")
                
                if validated_financials:
                    validated_financials.sort(key=lambda x: x['year'])
                    financial_history_json = json.dumps(validated_financials)
            
            # Insert startup data
            await db.execute(
                """
                INSERT INTO startups
                (user_id, company_name, description, industry, funding_goal,
                 funding_acquired, years_operating, website, logo_url, financial_history,
                 contact_phone, equity_offered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, company_name, user_data.description, user_data.industry,
                 user_data.funding_goal, user_data.funding_acquired, user_data.years_operating,
                 user_data.website, user_data.logo_url, financial_history_json,
                 user_data.contact_phone, user_data.equity_offered)
            )
        
        await db.commit()
        logger.info(f"User '{user_data.email}' registered successfully with ID: {user_id}")
        
        return {"message": "User registered successfully", "userId": user_id}

@app.post("/api/login", response_model=Token)
async def login(user_credentials: UserLogin):
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT * FROM users WHERE email = ?", (user_credentials.email,)) as cursor:
            user = await cursor.fetchone()
    
    if not user or not verify_password(user_credentials.password, user[2]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user[0])}, expires_delta=access_token_expires
    )
    
    logger.info(f"User '{user_credentials.email}' logged in successfully")
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/logout")
async def logout():
    # With JWT, logout is handled on client side by removing token
    return {"message": "Logout successful"}

@app.get("/api/auth/status", response_model=dict)
async def auth_status(current_user: dict = Depends(get_current_user)):
    return {
        "logged_in": True,
        "user": {
            "id": current_user["id"],
            "email": current_user["email"],
            "name": current_user["name"],
            "user_type": current_user["user_type"]
        }
    }

@app.get("/api/startups", response_model=List[StartupCard])
async def get_startups():
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("""
            SELECT id, user_id, company_name, description, industry, funding_goal,
                   funding_acquired, years_operating, website, logo_url, financial_history
            FROM startups ORDER BY created_at DESC
        """) as cursor:
            startup_rows = await cursor.fetchall()
    
    startups_with_risk = []
    for row in startup_rows:
        startup_dict = {
            'id': row[0],
            'user_id': row[1],
            'company_name': row[2],
            'description': row[3],
            'industry': row[4],
            'funding_goal': row[5],
            'funding_acquired': row[6],
            'years_operating': row[7],
            'website': row[8],
            'logo_url': row[9],
            'financial_history': []
        }
        
        # Parse financial history
        try:
            if row[10]:
                startup_dict['financial_history'] = json.loads(row[10])
        except json.JSONDecodeError:
            startup_dict['financial_history'] = []
        
        # Calculate risk
        risk_info = calculate_risk(startup_dict)
        
        # Create card data
        card_data = StartupCard(
            id=startup_dict['id'],
            company_name=startup_dict['company_name'],
            description=startup_dict.get('description', ''),
            industry=startup_dict.get('industry', ''),
            funding_goal=startup_dict.get('funding_goal', 0),
            funding_acquired=startup_dict.get('funding_acquired', 0),
            logo_url=startup_dict.get('logo_url', ''),
            risk_category=risk_info.get('category', 'Unknown')
        )
        startups_with_risk.append(card_data)
    
    return startups_with_risk

@app.get("/api/startups/{startup_id}", response_model=StartupDetail)
async def get_startup_details(startup_id: int, current_user: Optional[dict] = Depends(get_current_user_optional)):
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("""
            SELECT s.*, u.name as founder_name, u.email as founder_email
            FROM startups s
            JOIN users u ON s.user_id = u.id
            WHERE s.id = ?
        """, (startup_id,)) as cursor:
            startup_row = await cursor.fetchone()
    
    if not startup_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup not found"
        )
    
    # Build startup dict
    startup_dict = {
        'id': startup_row[0],
        'user_id': startup_row[1],
        'company_name': startup_row[2],
        'description': startup_row[3],
        'industry': startup_row[4],
        'funding_goal': startup_row[5],
        'funding_acquired': startup_row[6],
        'years_operating': startup_row[7],
        'website': startup_row[8],
        'logo_url': startup_row[9],
        'financial_history': [],
        'contact_phone': startup_row[11],
        'equity_offered': startup_row[12],
        'founder_name': startup_row[14],
        'founder_email': startup_row[15]
    }
    
    # Parse financial history
    try:
        if startup_row[10]:
            financial_data = json.loads(startup_row[10])
            startup_dict['financial_history'] = financial_data  # Keep as dict for risk calculation
    except json.JSONDecodeError:
        startup_dict['financial_history'] = []
    
    # Calculate risk and valuation
    startup_dict['risk_analysis'] = calculate_risk(startup_dict)
    startup_dict['calculated_valuation'] = calculate_valuation(startup_dict)
    
    # Convert financial history to Pydantic models for response
    try:
        if startup_row[10]:
            financial_data = json.loads(startup_row[10])
            startup_dict['financial_history'] = [
                FinancialRecord(**item) for item in financial_data
            ]
    except json.JSONDecodeError:
        startup_dict['financial_history'] = []
    
    # Check investor interest
    investor_has_expressed_interest = False
    if current_user and current_user.get('user_type') == 'investor':
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute(
                "SELECT 1 FROM investor_interest WHERE investor_user_id = ? AND startup_id = ?",
                (current_user['id'], startup_id)
            ) as cursor:
                interest = await cursor.fetchone()
                investor_has_expressed_interest = bool(interest)
    
    startup_dict['investor_has_expressed_interest'] = investor_has_expressed_interest
    
    return StartupDetail(**startup_dict)

@app.post("/api/startups/{startup_id}/interest")
async def express_interest(startup_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['user_type'] != 'investor':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only investors can express interest"
        )
    
    async with aiosqlite.connect(DATABASE) as db:
        # Check if startup exists
        async with db.execute("SELECT 1 FROM startups WHERE id = ?", (startup_id,)) as cursor:
            startup = await cursor.fetchone()
        
        if not startup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Startup not found"
            )
        
        # Express interest
        try:
            await db.execute(
                "INSERT INTO investor_interest (investor_user_id, startup_id) VALUES (?, ?)",
                (current_user['id'], startup_id)
            )
            await db.commit()
            logger.info(f"Investor {current_user['id']} expressed interest in startup {startup_id}")
            return {"message": "Interest expressed successfully"}
        except aiosqlite.IntegrityError:
            return {"message": "Already expressed interest"}

@app.delete("/api/startups/{startup_id}/interest")
async def withdraw_interest(startup_id: int, current_user: dict = Depends(get_current_user)):
    if current_user['user_type'] != 'investor':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only investors can withdraw interest"
        )
    
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "DELETE FROM investor_interest WHERE investor_user_id = ? AND startup_id = ?",
            (current_user['id'], startup_id)
        ) as cursor:
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Investor {current_user['id']} withdrew interest from startup {startup_id}")
                return {"message": "Interest withdrawn successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No interest found to withdraw"
                )

@app.get("/api/my-startup/analytics", response_model=Analytics)
async def get_my_startup_analytics(current_user: dict = Depends(get_current_user)):
    if current_user['user_type'] != 'startup':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only startups can access analytics"
        )
    
    async with aiosqlite.connect(DATABASE) as db:
        # Get startup ID
        async with db.execute("SELECT id FROM startups WHERE user_id = ?", (current_user['id'],)) as cursor:
            startup_row = await cursor.fetchone()
        
        if not startup_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Startup profile not found"
            )
        
        startup_id = startup_row[0]
        
        # Get interested investors
        async with db.execute("""
            SELECT u.name, u.email
            FROM investor_interest i
            JOIN users u ON i.investor_user_id = u.id
            WHERE i.startup_id = ? AND u.user_type = 'investor'
            ORDER BY i.expressed_at DESC
        """, (startup_id,)) as cursor:
            interested_investors = []
            async for row in cursor:
                interested_investors.append({
                    "name": row[0],
                    "email": row[1]
                })
    
    return Analytics(interested_investors=interested_investors)

@app.get("/api/my-startup", response_model=dict)
async def get_my_startup(current_user: dict = Depends(get_current_user)):
    if current_user['user_type'] != 'startup':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only startups can access this endpoint"
        )
    
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("""
            SELECT id, company_name, description, industry, funding_goal, funding_acquired,
                   years_operating, website, logo_url, contact_phone,
                   equity_offered, financial_history
            FROM startups WHERE user_id = ?
        """, (current_user['id'],)) as cursor:
            startup_data = await cursor.fetchone()
    
    if not startup_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Startup profile not found"
        )
    
    # Parse financial history
    financial_history = []
    try:
        if startup_data[11]:
            financial_history = json.loads(startup_data[11])
    except json.JSONDecodeError:
        pass
    
    return {
        "id": startup_data[0],
        "company_name": startup_data[1],
        "description": startup_data[2],
        "industry": startup_data[3],
        "funding_goal": startup_data[4],
        "funding_acquired": startup_data[5],
        "years_operating": startup_data[6],
        "website": startup_data[7],
        "logo_url": startup_data[8],
        "contact_phone": startup_data[9],
        "equity_offered": startup_data[10],
        "financial_history": financial_history
    }

@app.put("/api/my-startup")
async def update_my_startup(
    startup_update: StartupUpdate,
    current_user: dict = Depends(get_current_user)
):
    if current_user['user_type'] != 'startup':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only startups can update profiles"
        )
    
    # Build update query
    update_fields = []
    update_values = []
    
    for field, value in startup_update.dict(exclude_unset=True).items():
        update_fields.append(f"{field} = ?")
        update_values.append(value)
    
    if not update_fields:
        return {"message": "No fields provided for update"}
    
    update_values.append(current_user['id'])
    sql = f"UPDATE startups SET {', '.join(update_fields)} WHERE user_id = ?"
    
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(sql, tuple(update_values)) as cursor:
            await db.commit()
            
            if cursor.rowcount == 0:
                # Check if startup exists
                async with db.execute("SELECT 1 FROM startups WHERE user_id = ?", (current_user['id'],)) as check_cursor:
                    startup_exists = await check_cursor.fetchone()
                
                if not startup_exists:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Startup profile not found"
                    )
                else:
                    return {"message": "No changes detected in profile details"}
    
    logger.info(f"Startup profile updated successfully for user ID: {current_user['id']}")
    return {"message": "Startup profile details updated successfully"}

@app.put("/api/my-startup/financials")
async def update_my_startup_financials(
    financials_list: List[FinancialRecord],
    current_user: dict = Depends(get_current_user)
):
    if current_user['user_type'] != 'startup':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only startups can update financials"
        )
    
    # Validate and process financials
    validated_financials = []
    seen_years = set()
    
    for financial in financials_list:
        if financial.year in seen_years:
            logger.warning(f"Duplicate year {financial.year} found. Skipping.")
            continue
        seen_years.add(financial.year)
        validated_financials.append(financial.dict())
    
    # Sort by year
    validated_financials.sort(key=lambda x: x['year'])
    financial_history_json = json.dumps(validated_financials) if validated_financials else None
    
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "UPDATE startups SET financial_history = ? WHERE user_id = ?",
            (financial_history_json, current_user['id'])
        )
        await db.commit()
    
    logger.info(f"Successfully updated financial history for user {current_user['id']}")
    return {
        "message": "Financial history updated successfully",
        "updated_financials": validated_financials
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "CapitalBay API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="info")