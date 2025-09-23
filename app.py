from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from typing import List, Dict, Optional
from pydantic import BaseModel
import uuid
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import secrets
from datetime import timedelta
import requests
from fastapi.templating import Jinja2Templates
from typing import Optional
import hashlib
from datetime import datetime, timedelta






templates = Jinja2Templates(directory="templates")

# Configuration
SUPABASE_URL = "https://gbkhkbfbarsnpbdkxzii.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdia2hrYmZiYXJzbnBiZGt4emlpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzQzODAzNzMsImV4cCI6MjA0OTk1NjM3M30.mcOcC2GVEu_wD3xNBzSCC3MwDck3CIdmz4D8adU-bpI"

# Initialize clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Autocomplete Search API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create static directory if it doesn't exist
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic Models

class GoogleAuthRequest(BaseModel):
    google_token: str

class AuthenticatedRedeemRequest(BaseModel):
    google_token: str
    redemption_token: str

class SimpleRedeemRequest(BaseModel):
    email: str
    redemption_token: str


class InventoryItem(BaseModel):
    name: Optional[str]
    terex1: int
    precio: Optional[int] = None
    public_url_webp: Optional[str] = None
    estilo_id: Optional[int] = None
    color_id: Optional[int] = None

class SearchResult(BaseModel):
    modelo: str
    inventory_items: List[InventoryItem]
    total_inventory_items: int

class SearchRequest(BaseModel):
    modelo: str

class StyleSearchRequest(BaseModel):
    estilo: str

class CartItemRequest(BaseModel):
    item_name: str
    qty: int
    barcode: Optional[str] = None
    precio: Optional[int] = None
    modelo: Optional[str] = None
    estilo_id: Optional[int] = None
    color_id: Optional[int] = None
    terex1: Optional[int] = None
    public_url_webp: Optional[str] = None

class CartUpdateRequest(BaseModel):
    item_name: str
    new_qty: int

class CartRemoveRequest(BaseModel):
    item_name: str

class PopularStyle(BaseModel):
    estilo_id: int
    estilo: str
    total_qty: int
    public_url_webp: Optional[str] = None

class ImageModel(BaseModel):
    id: str  # Changed from int to str to handle UUID
    public_url_webp: str
    estilo_id: int
    color_id: int
    created_at: Optional[str] = None

class StoreBarcodeRequest(BaseModel):
    email: str
    barcode: str

class ValidateBarcodeRequest(BaseModel):
    barcode: str

class RedeemBarcodeRequest(BaseModel):
    barcode: str
    purchase_total: float
    order_id: Optional[int] = None

class BarcodeRedemptionResponse(BaseModel):
    success: bool
    message: str
    redeemed_amount: float
    remaining_balance: float
    user_email: str



user_sessions = {}



# Utility Functions
def generate_session_id(request: Request) -> str:
    """Generate a unique session ID based on IP and user agent"""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    timestamp = str(datetime.utcnow().timestamp())
    
    # Create a hash from IP, user agent, and timestamp
    session_data = f"{ip}_{user_agent}_{timestamp}"
    session_id = hashlib.md5(session_data.encode()).hexdigest()
    return session_id

async def get_or_create_session(request: Request) -> str:
    """Get existing session or create a new one"""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Try to find existing session based on IP and user agent from recent activity (today)
    existing_session = supabase.table("shop_user_cart_sessions").select("session_id").eq("ip_address", ip).eq("user_agent", user_agent).gte("last_activity", datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()).limit(1).execute()
    
    if existing_session.data:
        session_id = existing_session.data[0]["session_id"]
        # Update last activity
        supabase.table("shop_user_cart_sessions").update({
            "last_activity": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).eq("session_id", session_id).execute()
        return session_id
    
    # Create new session
    session_id = generate_session_id(request)
    
    session_data = {
        "session_id": session_id,
        "ip_address": ip,
        "user_agent": user_agent,
        "location_country": None,
        "location_city": None,
        "location_region": None,
        "cookies": {},
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat()
    }
    
    try:
        supabase.table("shop_user_cart_sessions").insert(session_data).execute()
        return session_id
    except Exception as e:
        print(f"Error creating session: {e}")
        return session_id

async def log_search_activity(request: Request, search_term: str, successful: bool, results_count: int = 0):
    """Log search activity to shop_search table"""
    try:
        session_id = await get_or_create_session(request)
        ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        search_log_data = {
            "session_id": session_id,
            "search_term": search_term,
            "search_successful": successful,
            "results_count": results_count,
            "ip_address": ip,
            "user_agent": user_agent,
            "searched_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("shop_search").insert(search_log_data).execute()
        
    except Exception as e:
        print(f"Error logging search activity: {e}")
        # Don't raise exception - logging shouldn't break the search functionality

# Cart Management Functions
async def add_to_cart(request: Request, item: CartItemRequest):
    """Add item to cart"""
    try:
        session_id = await get_or_create_session(request)
        
        # Check if item already exists in cart
        existing_item = supabase.table("shop_cart_items").select("*").eq("session_id", session_id).eq("name", item.item_name).execute()
        
        if existing_item.data:
            # Update quantity
            new_qty = existing_item.data[0]["qty"] + item.qty
            supabase.table("shop_cart_items").update({
                "qty": new_qty,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("session_id", session_id).eq("name", item.item_name).execute()
            
            return {"success": True, "message": "Item quantity updated", "session_id": session_id, "new_qty": new_qty}
        else:
            # Add new item
            cart_item_data = {
                "session_id": session_id,
                "qty": item.qty,
                "barcode": item.barcode,
                "name": item.item_name,
                "precio": item.precio,
                "modelo": item.modelo,
                "estilo_id": item.estilo_id,
                "color_id": item.color_id,
                "terex1": item.terex1,
                "public_url_webp": item.public_url_webp,
                "added_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("shop_cart_items").insert(cart_item_data).execute()
            return {"success": True, "message": "Item added to cart", "session_id": session_id, "qty": item.qty}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding to cart: {str(e)}")

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    """Serve the HTML interface"""
    try:
        # Try to find index.html in current directory first, then in templates folder
        html_file_paths = ["index.html", "templates/index.html", "static/index.html"]
        
        html_content = None
        for file_path in html_file_paths:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as file:
                    html_content = file.read()
                break
        
        if html_content is None:
            # Return a simple HTML page with instructions if no index.html is found
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Inventory Search</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                    .error { color: #d32f2f; background: #ffebee; padding: 20px; border-radius: 5px; }
                    .instructions { background: #e8f5e9; padding: 20px; border-radius: 5px; margin-top: 20px; }
                    code { background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }
                </style>
            </head>
            <body>
                <h1>Inventory Search API</h1>
                <div class="error">
                    <h3>⚠️ index.html file not found</h3>
                    <p>Please create an <code>index.html</code> file in your project directory.</p>
                </div>
                <div class="instructions">
                    <h3>📁 Recommended File Structure:</h3>
                    <pre>
your-project/
├── main.py              (this FastAPI file)
├── index.html           (your main HTML file)
└── static/
    ├── styles.css       (your CSS file)
    └── script.js        (your JavaScript file)
                    </pre>
                    <p><strong>Note:</strong> Make sure your HTML file references CSS and JS as:</p>
                    <ul>
                        <li><code>&lt;link rel="stylesheet" href="/static/styles.css"&gt;</code></li>
                        <li><code>&lt;script src="/static/script.js"&gt;&lt;/script&gt;</code></li>
                    </ul>
                </div>
                <p><strong>API Documentation:</strong> <a href="/docs">http://localhost:8000/docs</a></p>
            </body>
            </html>
            """
            
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error loading page</h1>
            <p>Error: {str(e)}</p>
            <p><a href="/docs">Visit API Documentation</a></p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)

@app.get("/api/modelos")
async def get_modelos():
    """Get all available modelos for autocomplete"""
    try:
        modelos_result = supabase.table("inventario_modelos").select("modelo").execute()
        modelos = [item["modelo"] for item in modelos_result.data if item["modelo"]]
        return {"modelos": sorted(list(set(modelos)))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching modelos: {str(e)}")

@app.get("/api/popular-styles")
async def get_popular_styles():
    """Get popular styles from inventario_estilos where prioridad = 1"""
    try:
        # Get all estilos with prioridad = 1
        estilos_result = supabase.table("inventario_estilos").select("id, nombre").eq("prioridad", 1).execute()
        
        if not estilos_result.data:
            return {"popular_styles": []}
        
        popular_styles = []
        
        for estilo_data in estilos_result.data:
            estilo_id = estilo_data.get("id")
            estilo_name = estilo_data.get("nombre")  # Changed from name to nombre
            
            # Get image for this style
            image_result = supabase.table("image_uploads").select("public_url_webp").eq("estilo_id", estilo_id).limit(1).execute()
            
            image_url = None
            if image_result.data:
                image_url = image_result.data[0]["public_url_webp"]
            
            popular_styles.append(PopularStyle(
                estilo_id=estilo_id,
                estilo=estilo_name,  # Using nombre as estilo
                total_qty=1,  # Just a placeholder since we're not counting sales
                public_url_webp=image_url
            ))
        
        # Sort by estilo name (you can change this)
        popular_styles.sort(key=lambda x: x.estilo)
        
        return {"popular_styles": popular_styles}
        
    except Exception as e:
        print(f"Error fetching popular styles: {e}")
        # Return empty list if there's an error
        return {"popular_styles": []}

@app.get("/api/images/{estilo_id}/{color_id}")
async def get_images_for_product(estilo_id: int, color_id: int):
    """Get all images for a specific estilo_id and color_id combination"""
    try:
        # Fetch all images for this estilo and color combination
        images_result = supabase.table("image_uploads").select("id, public_url_webp, estilo_id, color_id, created_at").eq("estilo_id", estilo_id).eq("color_id", color_id).order("created_at", desc=False).execute()
        
        if not images_result.data:
            return {"success": False, "message": "No images found for this product", "images": []}
        
        # Convert to ImageModel objects
        images = [
            ImageModel(
                id=img["id"],
                public_url_webp=img["public_url_webp"],
                estilo_id=img["estilo_id"],
                color_id=img["color_id"],
                created_at=img.get("created_at")
            ) for img in images_result.data if img.get("public_url_webp")
        ]
        
        return {
            "success": True, 
            "images": images,
            "total_images": len(images),
            "estilo_id": estilo_id,
            "color_id": color_id
        }
        
    except Exception as e:
        print(f"Error fetching images for estilo_id={estilo_id}, color_id={color_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching images: {str(e)}")

@app.post("/api/log-search")
async def log_search(request: Request, search_data: dict):
    """Log search activity when user clicks search button"""
    try:
        search_term = search_data.get("search_term", "")
        search_successful = search_data.get("search_successful", False)
        results_count = search_data.get("results_count", 0)
        
        await log_search_activity(request, search_term, search_successful, results_count)
        
        return {"success": True, "message": "Search logged successfully"}
        
    except Exception as e:
        print(f"Error in log_search endpoint: {e}")
        return {"success": False, "message": "Failed to log search"}

@app.post("/search", response_model=SearchResult)
async def search_inventory(request: SearchRequest):
    """Search for inventory items by exact modelo match with images always included"""
    
    modelo = request.modelo.strip()
    if not modelo:
        raise HTTPException(status_code=400, detail="Modelo cannot be empty")
    
    # Get inventory items for the modelo
    inventory_records = supabase.table("inventario1").select("name, terex1, precio, estilo_id, color_id, modelo").eq("modelo", modelo).gte("terex1", 1).execute()
    
    # Process inventory items and always add images
    processed_items = []
    for item in inventory_records.data:
        # Ensure we're getting the precio value correctly
        precio_value = item.get("precio")
        print(f"Processing item: {item.get('name')}, precio: {precio_value}, type: {type(precio_value)}")
        
        inventory_item = InventoryItem(
            name=item.get("name"),
            terex1=item.get("terex1", 0),
            precio=item.get("precio"),
            estilo_id=item.get("estilo_id"),
            color_id=item.get("color_id")
        )
        
        # Always try to get image if IDs are available
        if item.get("estilo_id") and item.get("color_id"):
            image_result = supabase.table("image_uploads").select("public_url_webp").eq("estilo_id", item["estilo_id"]).eq("color_id", item["color_id"]).limit(1).execute()
            if image_result.data:
                inventory_item.public_url_webp = image_result.data[0]["public_url_webp"]
        
        print(f"Created inventory_item with precio: {inventory_item.precio}")
        processed_items.append(inventory_item)
    
    return SearchResult(
        modelo=modelo,
        inventory_items=processed_items,
        total_inventory_items=len(processed_items)
    )

@app.post("/search-style", response_model=SearchResult)
async def search_inventory_by_style(request: StyleSearchRequest):
    """Search for inventory items by exact estilo match with terex1 > 0"""
    
    estilo = request.estilo.strip()
    if not estilo:
        raise HTTPException(status_code=400, detail="Estilo cannot be empty")
    
    # Get inventory items for the estilo where terex1 > 0
    inventory_records = supabase.table("inventario1").select("name, terex1, precio, estilo_id, color_id, estilo").eq("estilo", estilo).gt("terex1", 0).execute()
    
    # Process inventory items and always add images
    processed_items = []
    for item in inventory_records.data:
        # Ensure we're getting the precio value correctly
        precio_value = item.get("precio")
        print(f"Processing style item: {item.get('name')}, precio: {precio_value}, type: {type(precio_value)}")
        
        inventory_item = InventoryItem(
            name=item.get("name"),
            terex1=item.get("terex1", 0),
            precio=item.get("precio"),
            estilo_id=item.get("estilo_id"),
            color_id=item.get("color_id")
        )
        
        # Always try to get image if IDs are available
        if item.get("estilo_id") and item.get("color_id"):
            image_result = supabase.table("image_uploads").select("public_url_webp").eq("estilo_id", item["estilo_id"]).eq("color_id", item["color_id"]).limit(1).execute()
            if image_result.data:
                inventory_item.public_url_webp = image_result.data[0]["public_url_webp"]
        
        print(f"Created style inventory_item with precio: {inventory_item.precio}")
        processed_items.append(inventory_item)
    
    return SearchResult(
        modelo=estilo,  # Using modelo field to display the searched estilo
        inventory_items=processed_items,
        total_inventory_items=len(processed_items)
    )


# Cart API Endpoints
@app.post("/api/cart/add")
async def add_cart_item(request: Request, item: CartItemRequest):
    """Add item to cart"""
    return await add_to_cart(request, item)

@app.post("/api/cart/update")
async def update_cart_item(request: Request, update_data: CartUpdateRequest):
    """Update item quantity in cart"""
    try:
        session_id = await get_or_create_session(request)
        
        if update_data.new_qty <= 0:
            # Remove item if quantity is 0 or less
            supabase.table("shop_cart_items").delete().eq("session_id", session_id).eq("name", update_data.item_name).execute()
            return {"success": True, "message": "Item removed from cart", "session_id": session_id}
        else:
            # Update quantity
            supabase.table("shop_cart_items").update({
                "qty": update_data.new_qty,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("session_id", session_id).eq("name", update_data.item_name).execute()
            
            return {"success": True, "message": "Item quantity updated", "session_id": session_id, "new_qty": update_data.new_qty}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating cart: {str(e)}")

@app.post("/api/cart/remove")
async def remove_from_cart(request: Request, remove_data: CartRemoveRequest):
    """Remove item from cart"""
    try:
        session_id = await get_or_create_session(request)
        
        supabase.table("shop_cart_items").delete().eq("session_id", session_id).eq("name", remove_data.item_name).execute()
        
        return {"success": True, "message": "Item removed from cart", "session_id": session_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing from cart: {str(e)}")

@app.get("/api/cart")
async def get_cart(request: Request):
    """Get all cart items for current session"""
    try:
        session_id = await get_or_create_session(request)
        
        cart_items = supabase.table("shop_cart_items").select("*").eq("session_id", session_id).execute()
        
        return {"success": True, "session_id": session_id, "items": cart_items.data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cart: {str(e)}")

# Analytics Endpoints
@app.get("/api/analytics/search")
async def get_search_analytics(request: Request):
    """Get search analytics - popular searches, success rates, etc."""
    try:
        # Get all search data
        search_data = supabase.table("shop_search").select("*").order("searched_at", desc=True).limit(1000).execute()
        
        # Calculate analytics
        total_searches = len(search_data.data)
        successful_searches = len([s for s in search_data.data if s["search_successful"]])
        success_rate = (successful_searches / total_searches * 100) if total_searches > 0 else 0
        
        # Most popular search terms
        term_counts = {}
        unsuccessful_terms = []
        
        for search in search_data.data:
            term = search["search_term"]
            if term in term_counts:
                term_counts[term] += 1
            else:
                term_counts[term] = 1
                
            # Track unsuccessful searches
            if not search["search_successful"]:
                unsuccessful_terms.append(term)
        
        # Sort by popularity
        popular_terms = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Unique unsuccessful terms
        unique_unsuccessful = list(set(unsuccessful_terms))[:10]
        
        return {
            "success": True,
            "analytics": {
                "total_searches": total_searches,
                "successful_searches": successful_searches,
                "success_rate": round(success_rate, 2),
                "popular_search_terms": popular_terms,
                "unsuccessful_search_terms": unique_unsuccessful
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching search analytics: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "static_files_mounted": "/static",
        "docs_available": "/docs"
    }

def generate_session_token():
    """Generate a session token for authenticated users"""
    return secrets.token_urlsafe(32)

def get_current_user(session_token: str):
    """Get current user from session token"""
    if not session_token or session_token not in user_sessions:
        return None
    
    session = user_sessions[session_token]
    
    # Check if session expired
    if datetime.now() > session["expires_at"]:
        del user_sessions[session_token]
        return None
    
    return session

async def verify_google_token(token: str):
    """Verify Google JWT token and extract user info"""
    try:
        verify_response = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
        )
        
        if verify_response.status_code != 200:
            raise Exception("Invalid Google token")
            
        user_data = verify_response.json()
        
        return {
            "google_id": user_data["sub"],
            "email": user_data["email"],
            "name": user_data.get("name", ""),
            "picture": user_data.get("picture", "")
        }
        
    except Exception as e:
        raise Exception(f"Google token verification failed: {e}")

async def create_or_get_user(user_info: dict):
    """Create or get user in users table"""
    try:
        # Check if user already exists
        existing_user = supabase.table("users").select("*").eq("email", user_info['email']).limit(1).execute()
        
        if existing_user.data:
            return existing_user.data[0]
        
        # Create new user
        new_user_data = {
            "email": user_info["email"],
            "name": user_info["name"],
            "google_id": user_info["google_id"],
            "picture": user_info.get("picture", ""),
            "created_at": datetime.utcnow().isoformat()
        }
        
        created_user = supabase.table("users").insert(new_user_data).execute()
        return created_user.data[0] if created_user.data else created_user
        
    except Exception as e:
        raise Exception(f"Failed to create/get user: {e}")

# Add these new endpoints to your existing FastAPI app

@app.post("/api/auth/google")
async def google_auth(payload: GoogleAuthRequest):
    """Authenticate user with Google and create session"""
    try:
        # Verify Google token
        user_info = await verify_google_token(payload.google_token)
        
        # Create or get user
        user = await create_or_get_user(user_info)
        
        # Generate session token
        session_token = generate_session_token()
        user_sessions[session_token] = {
            "user_id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "expires_at": datetime.utcnow() + timedelta(hours=24)
        }
        
        return {
            "success": True,
            "session_token": session_token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/redeem")
async def simple_redeem_reward(payload: SimpleRedeemRequest):
    """Simple redemption without authentication"""
    try:
        # Get redemption data
        redemption = supabase.table("order_redemptions").select("order_id,email,purchase_total").eq("redemption_token", payload.redemption_token).limit(1).execute()
        
        if not redemption.data:
            raise HTTPException(status_code=400, detail="Token de redención no válido o expirado")
        
        redemption_data = redemption.data[0]
        
        # Check if already redeemed
        if redemption_data.get('email') and redemption_data.get('email').strip():
            raise HTTPException(status_code=400, detail="Esta recompensa ya ha sido canjeada")
        
        # Get order total
        order_items = supabase.table("ventas_terex1").select("qty,price").eq("order_id", redemption_data['order_id']).execute()
        
        if not order_items.data:
            raise HTTPException(status_code=400, detail="Orden no encontrada")
        
        order_total = sum(item['qty'] * item['price'] for item in order_items.data)
        reward_amount = order_total * 0.01
        
        # Create loyalty reward
        supabase.table("loyalty_rewards").insert({
            "order_id": redemption_data['order_id'],
            "email": payload.email,
            "purchase_amount": order_total,
            "reward_amount": reward_amount,
            "status": "active",
            "user_id": None
        }).execute()
        
        # Mark redemption as completed
        supabase.table("order_redemptions").update({
            "email": payload.email
        }).eq("redemption_token", payload.redemption_token).execute()
        
        return {
            "success": True,
            "order_id": redemption_data['order_id'],
            "total": order_total,
            "reward_amount": reward_amount,
            "email": payload.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/redeem/authenticated")
async def authenticated_redeem_reward(payload: AuthenticatedRedeemRequest):
    """Redeem reward with Google authentication"""
    try:
        # Verify Google token and get user info
        user_info = await verify_google_token(payload.google_token)
        
        # Create or get user
        user = await create_or_get_user(user_info)
        
        # Create session token
        session_token = generate_session_token()
        user_sessions[session_token] = {
            "user_id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "expires_at": datetime.utcnow() + timedelta(hours=24)
        }
        
        # Get redemption data (same logic as simple redeem)
        redemption = supabase.table("order_redemptions").select("order_id,email,purchase_total").eq("redemption_token", payload.redemption_token).limit(1).execute()
        
        if not redemption.data:
            raise HTTPException(status_code=400, detail="Token de redención no válido o expirado")
        
        redemption_data = redemption.data[0]
        
        if redemption_data.get('email') and redemption_data.get('email').strip():
            raise HTTPException(status_code=400, detail="Esta recompensa ya ha sido canjeada")
        
        # Get order total
        order_items = supabase.table("ventas_terex1").select("qty,price").eq("order_id", redemption_data['order_id']).execute()
        order_total = sum(item['qty'] * item['price'] for item in order_items.data)
        reward_amount = order_total * 0.01
        
        # Create loyalty reward with user_id
        supabase.table("loyalty_rewards").insert({
            "user_id": user["id"],
            "order_id": redemption_data['order_id'],
            "email": user["email"],
            "purchase_amount": order_total,
            "reward_amount": reward_amount,
            "status": "active"
        }).execute()
        
        # Mark redemption as completed
        supabase.table("order_redemptions").update({
            "email": user["email"]
        }).eq("redemption_token", payload.redemption_token).execute()
        
        return {
            "success": True,
            "order_id": redemption_data['order_id'],
            "total": order_total,
            "reward_amount": reward_amount,
            "session_token": session_token,
            "user": {
                "name": user["name"],
                "email": user["email"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/user/dashboard")
async def get_user_dashboard(session_token: str):
    """Get user dashboard data"""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    try:
        # Get user's rewards
        rewards = supabase.table("loyalty_rewards").select("*").eq("user_id", user['user_id']).order("created_at", desc=True).execute()
        
        # Calculate totals
        active_rewards = [r for r in rewards.data if r['status'] == 'active']
        total_earned = sum(r['reward_amount'] for r in rewards.data)
        total_available = sum(r['reward_amount'] for r in active_rewards)
        total_redeemed = sum(r['reward_amount'] for r in rewards.data if r['status'] == 'redeemed')
        
        return {
            "user": {
                "name": user["name"],
                "email": user["email"]
            },
            "summary": {
                "total_earned": total_earned,
                "total_available": total_available,
                "total_redeemed": total_redeemed,
                "rewards_count": len(rewards.data)
            },
            "recent_rewards": rewards.data[:10]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/user/rewards/{email}")
async def get_user_total_rewards(email: str):
    """Get total available rewards for a user by email"""
    try:
        rewards = supabase.table("loyalty_rewards").select("reward_amount,status,created_at,order_id").eq("email", email).order("created_at", desc=True).execute()
        
        active_rewards = [r for r in rewards.data if r['status'] == 'active']
        total_available = sum(r['reward_amount'] for r in active_rewards)
        
        return {
            "email": email,
            "total_available_rewards": total_available,
            "active_rewards_count": len(active_rewards),
            "all_rewards": rewards.data
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Debug endpoints
@app.get("/api/debug/sessions")
async def debug_sessions():
    """Debug endpoint to see active sessions"""
    active_sessions = {}
    current_time = datetime.utcnow()
    
    for token, session in user_sessions.items():
        if current_time < session["expires_at"]:
            active_sessions[token[:16] + "..."] = {
                "email": session["email"],
                "expires_in_minutes": int((session["expires_at"] - current_time).total_seconds() / 60)
            }
    
    return {
        "active_sessions": active_sessions,
        "total_active": len(active_sessions)
    }

@app.get("/redeem.html", response_class=HTMLResponse)
async def redeem_page(request: Request):
    return templates.TemplateResponse("redeem.html", {"request": request})

@app.get("/dashboard.html", response_class=HTMLResponse)  
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/test-dashboard")
async def test_dashboard():
    """Test dashboard with fake data"""
    fake_data = {
        "user": {
            "name": "Test User",
            "email": "test@example.com"
        },
        "summary": {
            "total_earned": 25.50,
            "total_available": 15.25,
            "total_redeemed": 10.25,
            "rewards_count": 3
        },
        "recent_rewards": [
            {
                "order_id": 12345,
                "purchase_amount": 100.00,
                "reward_amount": 1.00,
                "status": "active"
            },
            {
                "order_id": 12344,
                "purchase_amount": 150.00,
                "reward_amount": 1.50,
                "status": "redeemed"
            }
        ]
    }
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head><title>Test Dashboard</title></head>
    <body>
        <script>
            // Set a fake session token for testing
            localStorage.setItem('session_token', 'test-session-123');
            
            // Redirect to dashboard
            window.location.href = '/dashboard.html';
        </script>
    </body>
    </html>
    """)

@app.post("/api/user/store-barcode")
async def store_user_barcode(request: StoreBarcodeRequest):
    """Store or update user's barcode in the database"""
    try:
        # Check if user exists
        user_check = supabase.table("users").select("id").eq("email", request.email).limit(1).execute()
        
        if not user_check.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        user_id = user_check.data[0]["id"]
        
        # Check if barcode already exists for this user
        existing_barcode = supabase.table("user_barcodes").select("*").eq("user_email", request.email).limit(1).execute()
        
        if existing_barcode.data:
            # Update existing barcode
            supabase.table("user_barcodes").update({
                "barcode": request.barcode,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("user_email", request.email).execute()
        else:
            # Create new barcode entry
            barcode_data = {
                "user_id": user_id,
                "user_email": request.email,
                "barcode": request.barcode,
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            supabase.table("user_barcodes").insert(barcode_data).execute()
        
        return {"success": True, "message": "Código de barras almacenado exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing barcode: {str(e)}")

@app.post("/api/barcode/validate")
async def validate_barcode(request: ValidateBarcodeRequest):
    """Validate if barcode exists and get associated user info"""
    try:
        # Find barcode in database
        barcode_result = supabase.table("user_barcodes").select("user_email, status, user_id").eq("barcode", request.barcode).eq("status", "active").limit(1).execute()
        
        if not barcode_result.data:
            return {"success": False, "message": "Código de barras no válido o inactivo"}
        
        barcode_data = barcode_result.data[0]
        user_email = barcode_data["user_email"]
        
        # Get user's available rewards
        rewards_result = supabase.table("loyalty_rewards").select("reward_amount, status").eq("email", user_email).eq("status", "active").execute()
        
        total_available = sum(reward["reward_amount"] for reward in rewards_result.data)
        
        return {
            "success": True,
            "user_email": user_email,
            "available_balance": total_available,
            "active_rewards_count": len(rewards_result.data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating barcode: {str(e)}")

@app.post("/api/barcode/redeem", response_model=BarcodeRedemptionResponse)
async def redeem_with_barcode(request: RedeemBarcodeRequest):
    """Redeem rewards using barcode at point of sale"""
    try:
        # First validate the barcode
        barcode_result = supabase.table("user_barcodes").select("user_email, user_id").eq("barcode", request.barcode).eq("status", "active").limit(1).execute()
        
        if not barcode_result.data:
            raise HTTPException(status_code=400, detail="Código de barras no válido")
        
        user_email = barcode_result.data[0]["user_email"]
        user_id = barcode_result.data[0]["user_id"]
        
        # Get active rewards for this user
        active_rewards = supabase.table("loyalty_rewards").select("id, reward_amount").eq("email", user_email).eq("status", "active").order("created_at", desc=False).execute()
        
        if not active_rewards.data:
            return BarcodeRedemptionResponse(
                success=False,
                message="No hay recompensas disponibles para canjear",
                redeemed_amount=0.0,
                remaining_balance=0.0,
                user_email=user_email
            )
        
        total_available = sum(reward["reward_amount"] for reward in active_rewards.data)
        
        # Determine how much to redeem (up to purchase total or available balance)
        redeem_amount = min(request.purchase_total, total_available)
        
        if redeem_amount <= 0:
            return BarcodeRedemptionResponse(
                success=False,
                message="No hay suficiente saldo para canjear",
                redeemed_amount=0.0,
                remaining_balance=total_available,
                user_email=user_email
            )
        
        # Redeem rewards in FIFO order
        remaining_to_redeem = redeem_amount
        redeemed_rewards = []
        
        for reward in active_rewards.data:
            if remaining_to_redeem <= 0:
                break
                
            reward_amount = reward["reward_amount"]
            
            if reward_amount <= remaining_to_redeem:
                # Fully redeem this reward
                supabase.table("loyalty_rewards").update({
                    "status": "redeemed",
                    "redeemed_at": datetime.utcnow().isoformat()
                }).eq("id", reward["id"]).execute()
                
                remaining_to_redeem -= reward_amount
                redeemed_rewards.append(reward["id"])
            else:
                # Partially redeem this reward (split it)
                # Mark current reward as redeemed
                supabase.table("loyalty_rewards").update({
                    "status": "redeemed",
                    "redeemed_at": datetime.utcnow().isoformat(),
                    "reward_amount": remaining_to_redeem
                }).eq("id", reward["id"]).execute()
                
                # Create new reward with remaining amount
                remaining_amount = reward_amount - remaining_to_redeem
                new_reward_data = {
                    "user_id": user_id,
                    "email": user_email,
                    "purchase_amount": 0,  # This is a split reward
                    "reward_amount": remaining_amount,
                    "status": "active",
                    "order_id": 0  # Special marker for split rewards
                }
                supabase.table("loyalty_rewards").insert(new_reward_data).execute()
                
                remaining_to_redeem = 0
                redeemed_rewards.append(reward["id"])
        
        # Calculate new remaining balance
        new_balance = total_available - redeem_amount
        
        # Log the redemption transaction
        redemption_log = {
            "user_email": user_email,
            "barcode": request.barcode,
            "redeemed_amount": redeem_amount,
            "purchase_total": request.purchase_total,
            "order_id": request.order_id,
            "redeemed_at": datetime.utcnow().isoformat()
        }
        supabase.table("barcode_redemptions").insert(redemption_log).execute()
        
        return BarcodeRedemptionResponse(
            success=True,
            message=f"Se canjearon ${redeem_amount:.2f} en recompensas",
            redeemed_amount=redeem_amount,
            remaining_balance=new_balance,
            user_email=user_email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing barcode redemption: {str(e)}")


@app.get("/api/user/barcode/{email}")
async def get_user_barcode(email: str):
    """Get user's barcode by email - handles both linked and unlinked barcodes"""
    try:
        # Look for ANY barcode for this email, regardless of user_id
        barcode_result = supabase.table("user_barcodes").select("barcode, created_at, updated_at, user_id").eq("user_email", email).eq("status", "active").limit(1).execute()
        
        if not barcode_result.data:
            return {"success": False, "message": "No barcode found for user"}
        
        barcode_data = barcode_result.data[0]
        
        # If the user is accessing via dashboard and barcode has no user_id, link it
        if barcode_data.get("user_id") is None:
            try:
                # Try to link the barcode to the user account
                user_check = supabase.table("users").select("id").eq("email", email).limit(1).execute()
                
                if user_check.data:
                    user_id = user_check.data[0]["id"]
                    
                    # Update the barcode to link it to the user account
                    supabase.table("user_barcodes").update({
                        "user_id": user_id,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("user_email", email).eq("barcode", barcode_data["barcode"]).execute()
                    
                    print(f"DEBUG: Auto-linked barcode to user account for {email}")
            except Exception as link_error:
                print(f"DEBUG: Failed to auto-link barcode: {link_error}")
                # Continue anyway, barcode still works
        
        return {
            "success": True,
            "barcode": barcode_data["barcode"],
            "created_at": barcode_data["created_at"],
            "updated_at": barcode_data["updated_at"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user barcode: {str(e)}")




@app.get("/api/barcode/redemption-history/{email}")
async def get_barcode_redemption_history(email: str):
    """Get barcode redemption history for a user"""
    try:
        history = supabase.table("barcode_redemptions").select("*").eq("user_email", email).order("redeemed_at", desc=True).limit(50).execute()
        
        return {
            "success": True,
            "redemption_history": history.data,
            "total_redeemed": sum(item["redeemed_amount"] for item in history.data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching redemption history: {str(e)}")

# Add this utility function to generate consistent barcodes
def generate_user_barcode(email: str, timestamp: str = None) -> str:
    """Generate a consistent barcode for a user based on email"""
    if timestamp is None:
        timestamp = str(datetime.utcnow().timestamp())
    
    # Create hash from email and timestamp
    hash_input = f"{email}_{timestamp}"
    hash_object = hashlib.md5(hash_input.encode())
    hash_hex = hash_object.hexdigest()
    
    # Extract digits and ensure we have enough
    digits = ''.join(filter(str.isdigit, hash_hex))
    if len(digits) < 9:
        # Pad with hash characters converted to numbers
        for char in hash_hex:
            if not char.isdigit():
                digits += str(ord(char) % 10)
            if len(digits) >= 9:
                break
    
    # Take first 9 digits and create EAN-13 format: 7000 + 9 digits
    barcode_number = f"7000{digits[:9]}"
    
    # Calculate EAN-13 check digit
    check_digit = calculate_ean13_check_digit(barcode_number)
    
    return f"{barcode_number}{check_digit}"

def calculate_ean13_check_digit(barcode: str) -> int:
    """Calculate EAN-13 check digit"""
    odd_sum = sum(int(barcode[i]) for i in range(0, len(barcode), 2))
    even_sum = sum(int(barcode[i]) for i in range(1, len(barcode), 2))
    total = odd_sum + (even_sum * 3)
    return (10 - (total % 10)) % 10


@app.post("/api/auth/dashboard")
async def dashboard_auth(payload: GoogleAuthRequest):
    """Authenticate user with Google for dashboard access (no redemption required)"""
    try:
        print(f"DEBUG: Dashboard auth request received", flush=True)
        
        # Verify Google token
        print(f"DEBUG: Verifying Google token", flush=True)
        user_info = await verify_google_token(payload.google_token)
        print(f"DEBUG: Google token verified for {user_info.get('email')}", flush=True)
        
        # Create or get user
        print(f"DEBUG: Creating/getting user", flush=True)
        user = await create_or_get_user(user_info)
        print(f"DEBUG: User created/retrieved: {user.get('email')}", flush=True)
        
        # Generate session token
        session_token = generate_session_token()
        user_sessions[session_token] = {
            "user_id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "expires_at": datetime.utcnow() + timedelta(hours=24)
        }
        print(f"DEBUG: Session token created", flush=True)
        
        # Ensure user has a barcode (create if missing)
        try:
            await ensure_user_barcode(user["email"])
            print(f"DEBUG: Barcode ensured for user", flush=True)
        except Exception as barcode_error:
            print(f"DEBUG: Barcode creation failed: {barcode_error}", flush=True)
            # Continue anyway - barcode creation failure shouldn't block dashboard access
        
        return {
            "success": True,
            "session_token": session_token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"]
            }
        }
        
    except Exception as e:
        print(f"DEBUG: Dashboard auth error: {str(e)}", flush=True)
        import traceback
        print(f"DEBUG: Full traceback:", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


async def ensure_user_barcode(email: str):
    """Ensure user has a barcode, create if missing, link existing ones to user account"""
    try:
        # First, check if there's ANY barcode for this email (user_id can be NULL or set)
        existing_barcode = supabase.table("user_barcodes").select("*").eq("user_email", email).eq("status", "active").limit(1).execute()
        
        if existing_barcode.data:
            barcode_record = existing_barcode.data[0]
            
            # If barcode exists but has no user_id, link it to the user account
            if barcode_record.get("user_id") is None:
                # Get the user_id for this email
                user_check = supabase.table("users").select("id").eq("email", email).limit(1).execute()
                
                if user_check.data:
                    user_id = user_check.data[0]["id"]
                    
                    # Update the barcode to link it to the user account
                    supabase.table("user_barcodes").update({
                        "user_id": user_id,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("id", barcode_record["id"]).execute()
                    
                    print(f"DEBUG: Linked existing barcode to user account for {email}")
            
            return barcode_record["barcode"]
        
        # No barcode exists, create a new one
        user_check = supabase.table("users").select("id").eq("email", email).limit(1).execute()
        
        if not user_check.data:
            print(f"DEBUG: No user found for email {email}")
            return None
        
        user_id = user_check.data[0]["id"]
        new_barcode = generate_user_barcode(email)
        
        barcode_data = {
            "user_id": user_id,
            "user_email": email,
            "barcode": new_barcode,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("user_barcodes").insert(barcode_data).execute()
        print(f"DEBUG: Created new barcode for {email}: {new_barcode}")
        return new_barcode
        
    except Exception as e:
        print(f"Error ensuring user barcode for {email}: {e}")
        return None

# Also add this new function to handle barcode creation for simple redemptions:

async def ensure_barcode_for_email(email: str):
    """Ensure an email has a barcode, create if missing (for simple redemptions without user accounts)"""
    try:
        # Check if email already has a barcode (any barcode, regardless of user_id)
        existing_barcode = supabase.table("user_barcodes").select("barcode").eq("user_email", email).eq("status", "active").limit(1).execute()
        
        if existing_barcode.data:
            print(f"DEBUG: Barcode already exists for email {email}")
            return existing_barcode.data[0]["barcode"]
        
        # Generate new barcode for this email
        new_barcode = generate_user_barcode(email)
        
        # Create barcode entry without user_id (since this is for simple redemption)
        barcode_data = {
            "user_id": None,  # No user account for simple redemptions
            "user_email": email,
            "barcode": new_barcode,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("user_barcodes").insert(barcode_data).execute()
        print(f"DEBUG: Created barcode for email {email}: {new_barcode}")
        return new_barcode
        
    except Exception as e:
        print(f"Error ensuring barcode for email {email}: {e}")
        raise e    """Ensure user has a barcode, create if missing"""
    try:
        # Check if user already has a barcode
        existing_barcode = supabase.table("user_barcodes").select("barcode").eq("user_email", email).eq("status", "active").limit(1).execute()
        
        if existing_barcode.data:
            return existing_barcode.data[0]["barcode"]
        
        # Create new barcode if none exists
        user_check = supabase.table("users").select("id").eq("email", email).limit(1).execute()
        
        if not user_check.data:
            return None
        
        user_id = user_check.data[0]["id"]
        new_barcode = generate_user_barcode(email)
        
        barcode_data = {
            "user_id": user_id,
            "user_email": email,
            "barcode": new_barcode,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("user_barcodes").insert(barcode_data).execute()
        return new_barcode
        
    except Exception as e:
        print(f"Error ensuring user barcode: {e}")
        return None

if __name__ == "__main__":
    import uvicorn  
    uvicorn.run(app, host="0.0.0.0", port=8000)