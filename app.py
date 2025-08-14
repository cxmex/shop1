from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from typing import List, Dict, Optional
from pydantic import BaseModel
import uuid
import hashlib
import json
from datetime import datetime

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

class InventoryItem(BaseModel):
    name: Optional[str]
    terex1: int
    precio: Optional[int] = None
    public_url_webp: Optional[str] = None

class SearchResult(BaseModel):
    modelo: str
    inventory_items: List[InventoryItem]
    total_inventory_items: int

class SearchRequest(BaseModel):
    modelo: str

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
    
    # Try to find existing session based on IP and user agent from recent activity
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

@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    """Serve the HTML interface"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Autocomplete Search - Inventory</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
            }
            .search-box {
                margin-bottom: 20px;
                position: relative;
            }
            input[type="text"] {
                width: 100%;
                padding: 15px;
                font-size: 16px;
                border: 2px solid #ddd;
                border-radius: 8px;
                box-sizing: border-box;
            }
            input[type="text"]:focus {
                outline: none;
                border-color: #4CAF50;
            }
            .autocomplete-dropdown {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 1px solid #ddd;
                border-top: none;
                border-radius: 0 0 8px 8px;
                max-height: 200px;
                overflow-y: auto;
                z-index: 1000;
                display: none;
            }
            .autocomplete-item {
                padding: 12px 15px;
                cursor: pointer;
                border-bottom: 1px solid #f0f0f0;
            }
            .autocomplete-item:hover {
                background-color: #f5f5f5;
            }
            .autocomplete-item.selected {
                background-color: #4CAF50;
                color: white;
            }
            .autocomplete-item:last-child {
                border-bottom: none;
            }
            button {
                width: 100%;
                padding: 15px;
                font-size: 16px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                margin-top: 10px;
            }
            button:hover {
                background-color: #45a049;
            }
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            .loading {
                text-align: center;
                color: #666;
                margin: 20px 0;
            }
            .results {
                margin-top: 30px;
            }
            .match-info {
                background-color: #e8f5e8;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #4CAF50;
            }
            .inventory-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }
            .inventory-item {
                display: flex;
                align-items: center;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-bottom: 15px;
                background: white;
                transition: box-shadow 0.3s;
            }
            .inventory-item:hover {
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .item-image-container {
                flex-shrink: 0;
                margin-right: 20px;
            }
            .item-image {
                width: 100px;
                height: 100px;
                object-fit: cover;
                border-radius: 6px;
                border: 1px solid #ddd;
            }
            .item-content {
                flex-grow: 1;
                display: flex;
                flex-direction: column;
                justify-content: center;
                gap: 8px;
            }
            .item-details {
                width: 100%;
            }
            .item-name {
                font-size: 14px;
                font-weight: 400;
                color: #666;
                margin-bottom: 8px;
                text-transform: none;
            }
            .item-actions {
                display: flex;
                flex-direction: column;
                gap: 10px;
                width: 100%;
            }
            .item-qty-price {
                display: flex;
                align-items: center;
                gap: 15px;
                margin-bottom: 10px;
            }
            .item-qty {
                font-size: 16px;
                color: #666;
                font-weight: 500;
            }
            .item-price {
                font-size: 20px;
                color: #333;
                font-weight: 600;
            }
            .cart-button {
                background-color: #FFD700;
                color: #333;
                border: 2px solid #FFD700;
                padding: 8px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: all 0.3s;
                min-height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }
            .cart-button:hover {
                background-color: #FFC107;
            }
            .cart-button.active {
                background-color: white;
                color: #333;
                border: 2px solid #FFD700;
            }
            .quantity-controls-inline {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .qty-btn-inline {
                background-color: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
                color: #333;
                cursor: pointer;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 2px;
                transition: background-color 0.2s;
            }
            .qty-btn-inline:hover {
                background-color: rgba(0,0,0,0.1);
            }
            .qty-btn-inline:disabled {
                opacity: 0.3;
                cursor: not-allowed;
            }
            .qty-display-inline {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                min-width: 20px;
                text-align: center;
            }
            .bin-icon {
                width: 16px;
                height: 16px;
                fill: currentColor;
            }
            .no-results {
                text-align: center;
                color: #666;
                padding: 40px;
                background-color: #f8f9fa;
                border-radius: 8px;
            }
            .error {
                background-color: #ffe6e6;
                color: #d32f2f;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #d32f2f;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Buscar Inventario</h1>
            
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Type to search modelos..." autocomplete="off" />
                <div id="autocompleteDropdown" class="autocomplete-dropdown"></div>
                
                <button onclick="performSearch()" id="searchButton" style="background-color: #FFD700; color: #333;">Buscar</button>
            </div>
            
            <div id="loading" class="loading" style="display: none;">
                Searching... Please wait
            </div>
            
            <div id="results" class="results"></div>
        </div>

        <script>
            let allModelos = [];
            let selectedModeloIndex = -1;
            let filteredModelos = [];
            let itemQuantities = {};
            
            // Load all modelos on page load
            async function loadModelos() {
                try {
                    const response = await fetch('/api/modelos');
                    const data = await response.json();
                    allModelos = data.modelos;
                } catch (error) {
                    console.error('Error loading modelos:', error);
                }
            }
            
            async function logSearchActivity(searchTerm, successful, resultsCount) {
                try {
                    await fetch('/api/log-search', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            search_term: searchTerm,
                            search_successful: successful,
                            results_count: resultsCount
                        })
                    });
                } catch (error) {
                    console.log('Failed to log search activity:', error);
                    // Don't show error to user - logging is background functionality
                }
            }
            
            // Initialize page
            document.addEventListener('DOMContentLoaded', loadModelos);
            
            // Search input event listeners
            const searchInput = document.getElementById('searchInput');
            const dropdown = document.getElementById('autocompleteDropdown');
            
            searchInput.addEventListener('input', function() {
                const query = this.value.trim();
                if (query.length === 0) {
                    hideDropdown();
                    return;
                }
                
                // Filter modelos
                filteredModelos = allModelos.filter(modelo => 
                    modelo.toLowerCase().includes(query.toLowerCase())
                );
                
                showDropdown(filteredModelos);
                selectedModeloIndex = -1;
            });
            
            searchInput.addEventListener('keydown', function(e) {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    selectedModeloIndex = Math.min(selectedModeloIndex + 1, filteredModelos.length - 1);
                    updateSelection();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    selectedModeloIndex = Math.max(selectedModeloIndex - 1, -1);
                    updateSelection();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    if (selectedModeloIndex >= 0) {
                        selectModelo(filteredModelos[selectedModeloIndex]);
                    } else {
                        performSearch();
                    }
                } else if (e.key === 'Escape') {
                    hideDropdown();
                }
            });
            
            // Click outside to close dropdown
            document.addEventListener('click', function(e) {
                if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                    hideDropdown();
                }
            });
            
            function showDropdown(modelos) {
                if (modelos.length === 0) {
                    hideDropdown();
                    return;
                }
                
                dropdown.innerHTML = '';
                modelos.slice(0, 10).forEach((modelo, index) => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item';
                    item.textContent = modelo;
                    item.addEventListener('click', () => selectModelo(modelo));
                    dropdown.appendChild(item);
                });
                
                dropdown.style.display = 'block';
            }
            
            function hideDropdown() {
                dropdown.style.display = 'none';
                selectedModeloIndex = -1;
            }
            
            function updateSelection() {
                const items = dropdown.querySelectorAll('.autocomplete-item');
                items.forEach((item, index) => {
                    if (index === selectedModeloIndex) {
                        item.classList.add('selected');
                    } else {
                        item.classList.remove('selected');
                    }
                });
            }
            
            function selectModelo(modelo) {
                searchInput.value = modelo;
                hideDropdown();
                performSearch();
            }
            
            async function performSearch() {
                const searchInput = document.getElementById('searchInput');
                const searchButton = document.getElementById('searchButton');
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                
                const modelo = searchInput.value.trim();
                
                if (!modelo) {
                    alert('Please select a modelo');
                    return;
                }
                
                // Reset quantities when performing new search
                itemQuantities = {};
                
                // Show loading state
                searchButton.disabled = true;
                loading.style.display = 'block';
                results.innerHTML = '';
                
                try {
                    const response = await fetch('/search', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            modelo: modelo
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok) {
                        throw new Error(data.detail || 'Search failed');
                    }
                    
                    displayResults(data);
                    
                    // Store search results globally for cart operations
                    window.currentSearchResults = data;
                    
                    // Log search activity
                    logSearchActivity(modelo, data.total_inventory_items > 0, data.total_inventory_items);
                    
                } catch (error) {
                    results.innerHTML = `
                        <div class="error">
                            <strong>Error:</strong> ${error.message}
                        </div>
                    `;
                    
                    // Log unsuccessful search
                    logSearchActivity(modelo, false, 0);
                } finally {
                    // Hide loading state
                    searchButton.disabled = false;
                    loading.style.display = 'none';
                }
            }
            
            function displayResults(data) {
                const results = document.getElementById('results');
                
                if (data.total_inventory_items === 0) {
                    results.innerHTML = `
                        <div class="no-results">
                            <h3>No inventory items found</h3>
                            <p>No items found for modelo "${data.modelo}" with terex1 >= 1</p>
                        </div>
                    `;
                    return;
                }
                
                let html = `
                    <div class="match-info">
                        <h3>✅ Found: ${data.modelo}</h3>
                        <p><strong>Inventory Items Found:</strong> ${data.total_inventory_items}</p>
                    </div>
                `;
                
                if (data.inventory_items.length > 0) {
                    html += `<div class="inventory-container">`;
                    
                    data.inventory_items.forEach((item, index) => {
                        const itemName = item.name || 'N/A';
                        const itemId = `item_${index}`;
                        const precio = item.precio ? `$${item.precio}` : 'N/A';
                        
                        // Initialize quantity for this item if not exists
                        if (!itemQuantities[itemId]) {
                            itemQuantities[itemId] = 1;
                        }
                        
                        html += `
                            <div class="inventory-item">
                                <div class="item-image-container">
                        `;
                        
                        if (item.public_url_webp) {
                            html += `<img src="${item.public_url_webp}" alt="Item image" class="item-image">`;
                        } else {
                            html += `<div class="item-image" style="background-color: #f0f0f0; display: flex; align-items: center; justify-content: center; color: #999;">No image</div>`;
                        }
                        
                        html += `
                                </div>
                                <div class="item-content">
                                    <div class="item-name">${itemName}</div>
                                    <div class="item-qty-price">
                                        <div class="item-qty">${item.terex1} in stock</div>
                                        <div class="item-price">${precio}</div>
                                    </div>
                                    <button class="cart-button" id="btn_${itemId}" onclick="addToCart('${itemId}', '${itemName}', ${item.terex1}, '${item.public_url_webp || ''}', ${item.precio || 0})">
                                        Add to Cart
                                    </button>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += `</div>`;
                }
                
                results.innerHTML = html;
            }
            
            function addToCart(itemId, itemName, maxStock, imageUrl, precio) {
                const button = document.getElementById(`btn_${itemId}`);
                
                // Initialize quantity
                itemQuantities[itemId] = 1;
                
                // Change button to show quantity controls
                button.classList.add('active');
                
                // Replace button content with quantity controls
                if (itemQuantities[itemId] === 1) {
                    // Show bin icon instead of minus when quantity is 1
                    button.innerHTML = `
                        <div class="quantity-controls-inline">
                            <div class="qty-btn-inline" onclick="event.stopPropagation(); removeFromCart('${itemId}')">
                                <svg class="bin-icon" viewBox="0 0 24 24">
                                    <path d="M6 7H5V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1h-1V6a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1z"/>
                                    <path d="M19 7H5a1 1 0 0 0-1 1v11a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V8a1 1 0 0 0-1-1zM7 19a1 1 0 0 1-1-1V9h2v10H7zm4 0H9V9h2v10zm4 0h-2V9h2v10zm2-1a1 1 0 0 1-1 1V9h2v9z"/>
                                </svg>
                            </div>
                            <span class="qty-display-inline">${itemQuantities[itemId]}</span>
                            <button class="qty-btn-inline" onclick="event.stopPropagation(); incrementQuantity('${itemId}', ${maxStock})">+</button>
                        </div>
                    `;
                }
                
                // Send to database
                sendCartToDatabase(itemId, itemName, itemQuantities[itemId], precio, maxStock, imageUrl, 'add');
            }
            
            function removeFromCart(itemId) {
                const button = document.getElementById(`btn_${itemId}`);
                
                // Get item name for database removal
                const itemName = getItemNameFromId(itemId);
                
                // Reset button to original state
                button.classList.remove('active');
                button.innerHTML = 'Add to Cart';
                
                // Send removal to database
                sendCartToDatabase(itemId, itemName, 0, 0, 0, '', 'remove');
                
                // Reset quantity
                delete itemQuantities[itemId];
            }
            
            function incrementQuantity(itemId, maxStock) {
                if (itemQuantities[itemId] < maxStock) {
                    itemQuantities[itemId]++;
                    updateButtonDisplay(itemId, maxStock);
                    
                    // Update database
                    const itemName = getItemNameFromId(itemId);
                    sendCartToDatabase(itemId, itemName, itemQuantities[itemId], 0, maxStock, '', 'update');
                }
            }
            
            function decrementQuantity(itemId, maxStock) {
                if (itemQuantities[itemId] > 1) {
                    itemQuantities[itemId]--;
                    updateButtonDisplay(itemId, maxStock);
                    
                    // Update database
                    const itemName = getItemNameFromId(itemId);
                    sendCartToDatabase(itemId, itemName, itemQuantities[itemId], 0, maxStock, '', 'update');
                }
            }
            
            function getItemNameFromId(itemId) {
                // Extract item name from the DOM or store it globally
                const itemIndex = itemId.replace('item_', '');
                const inventoryItems = window.currentSearchResults?.inventory_items || [];
                if (inventoryItems[itemIndex]) {
                    return inventoryItems[itemIndex].name || 'Unknown Item';
                }
                return 'Unknown Item';
            }
            
            async function sendCartToDatabase(itemId, itemName, qty, precio, maxStock, imageUrl, action) {
                try {
                    const inventoryItems = window.currentSearchResults?.inventory_items || [];
                    const itemIndex = parseInt(itemId.replace('item_', ''));
                    const item = inventoryItems[itemIndex];
                    
                    if (action === 'add') {
                        const response = await fetch('/api/cart/add', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                item_name: itemName,
                                qty: qty,
                                barcode: null,
                                precio: precio,
                                modelo: window.currentSearchResults?.modelo || null,
                                estilo_id: item?.estilo_id || null,
                                color_id: item?.color_id || null,
                                terex1: maxStock,
                                public_url_webp: imageUrl
                            })
                        });
                        
                        const result = await response.json();
                        if (!result.success) {
                            console.error('Failed to add to cart:', result);
                        }
                    } else if (action === 'update') {
                        const response = await fetch('/api/cart/update', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                item_name: itemName,
                                new_qty: qty
                            })
                        });
                        
                        const result = await response.json();
                        if (!result.success) {
                            console.error('Failed to update cart:', result);
                        }
                    } else if (action === 'remove') {
                        const response = await fetch('/api/cart/remove', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                item_name: itemName
                            })
                        });
                        
                        const result = await response.json();
                        if (!result.success) {
                            console.error('Failed to remove from cart:', result);
                        }
                    }
                } catch (error) {
                    console.error('Error sending cart data to database:', error);
                }
            }
            
            function updateButtonDisplay(itemId, maxStock) {
                const button = document.getElementById(`btn_${itemId}`);
                const quantity = itemQuantities[itemId];
                
                if (quantity === 1) {
                    // Show bin icon instead of minus when quantity is 1
                    button.innerHTML = `
                        <div class="quantity-controls-inline">
                            <div class="qty-btn-inline" onclick="event.stopPropagation(); removeFromCart('${itemId}')">
                                <svg class="bin-icon" viewBox="0 0 24 24">
                                    <path d="M6 7H5V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1h-1V6a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1z"/>
                                    <path d="M19 7H5a1 1 0 0 0-1 1v11a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V8a1 1 0 0 0-1-1zM7 19a1 1 0 0 1-1-1V9h2v10H7zm4 0H9V9h2v10zm4 0h-2V9h2v10zm2-1a1 1 0 0 1-1 1V9h2v9z"/>
                                </svg>
                            </div>
                            <span class="qty-display-inline">${quantity}</span>
                            <button class="qty-btn-inline" onclick="event.stopPropagation(); incrementQuantity('${itemId}', ${maxStock})" ${quantity >= maxStock ? 'disabled' : ''}>+</button>
                        </div>
                    `;
                } else {
                    // Show normal minus button when quantity > 1
                    button.innerHTML = `
                        <div class="quantity-controls-inline">
                            <button class="qty-btn-inline" onclick="event.stopPropagation(); decrementQuantity('${itemId}', ${maxStock})">−</button>
                            <span class="qty-display-inline">${quantity}</span>
                            <button class="qty-btn-inline" onclick="event.stopPropagation(); incrementQuantity('${itemId}', ${maxStock})" ${quantity >= maxStock ? 'disabled' : ''}>+</button>
                        </div>
                    `;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/modelos")
async def get_modelos():
    """Get all available modelos for autocomplete"""
    try:
        modelos_result = supabase.table("inventario_modelos").select("modelo").execute()
        modelos = [item["modelo"] for item in modelos_result.data if item["modelo"]]
        return {"modelos": sorted(list(set(modelos)))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching modelos: {str(e)}")

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
async def get_modelos():
    """Get all available modelos for autocomplete"""
    try:
        modelos_result = supabase.table("inventario_modelos").select("modelo").execute()
        modelos = [item["modelo"] for item in modelos_result.data if item["modelo"]]
        return {"modelos": sorted(list(set(modelos)))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching modelos: {str(e)}")

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
            precio=item.get("precio")
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

if __name__ == "__main__":
    import uvicorn  
    uvicorn.run(app, host="0.0.0.0", port=8000)