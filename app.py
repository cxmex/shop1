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

if __name__ == "__main__":
    import uvicorn  
    uvicorn.run(app, host="0.0.0.0", port=8000)