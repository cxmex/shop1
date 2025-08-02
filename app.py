from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from typing import List, Dict, Optional
from pydantic import BaseModel

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
    barcode: Optional[str]
    terex1: int
    modelo: str
    estilo: Optional[str]
    color: Optional[str]
    estilo_id: Optional[int]
    color_id: Optional[int]
    public_url: Optional[str] = None

class SearchResult(BaseModel):
    modelo: str
    inventory_items: List[InventoryItem]
    total_inventory_items: int

class SearchRequest(BaseModel):
    modelo: str
    con_imagenes: bool = False

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
            .toggle-container {
                display: flex;
                align-items: center;
                margin: 15px 0;
                gap: 10px;
            }
            .toggle-switch {
                position: relative;
                display: inline-block;
                width: 60px;
                height: 34px;
            }
            .toggle-switch input {
                opacity: 0;
                width: 0;
                height: 0;
            }
            .slider {
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: #ccc;
                transition: .4s;
                border-radius: 34px;
            }
            .slider:before {
                position: absolute;
                content: "";
                height: 26px;
                width: 26px;
                left: 4px;
                bottom: 4px;
                background-color: white;
                transition: .4s;
                border-radius: 50%;
            }
            input:checked + .slider {
                background-color: #4CAF50;
            }
            input:checked + .slider:before {
                transform: translateX(26px);
            }
            .toggle-label {
                font-size: 16px;
                font-weight: 500;
                color: #333;
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
            .inventory-table th,
            .inventory-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
                vertical-align: top;
            }
            .inventory-table th {
                background-color: #f8f9fa;
                font-weight: 600;
            }
            .inventory-table tr:hover {
                background-color: #f5f5f5;
            }
            .item-image {
                max-width: 120px;
                max-height: 120px;
                object-fit: cover;
                border-radius: 4px;
                border: 1px solid #ddd;
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
            <h1>🔍 Autocomplete Search - Inventory System</h1>
            
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Type to search modelos..." autocomplete="off" />
                <div id="autocompleteDropdown" class="autocomplete-dropdown"></div>
                
                <div class="toggle-container">
                    <span class="toggle-label">Con Imágenes</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="imageToggle">
                        <span class="slider"></span>
                    </label>
                </div>
                
                <button onclick="performSearch()" id="searchButton">Search</button>
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
                const imageToggle = document.getElementById('imageToggle');
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                
                const modelo = searchInput.value.trim();
                
                if (!modelo) {
                    alert('Please select a modelo');
                    return;
                }
                
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
                            modelo: modelo,
                            con_imagenes: imageToggle.checked
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok) {
                        throw new Error(data.detail || 'Search failed');
                    }
                    
                    displayResults(data, imageToggle.checked);
                    
                } catch (error) {
                    results.innerHTML = `
                        <div class="error">
                            <strong>Error:</strong> ${error.message}
                        </div>
                    `;
                } finally {
                    // Hide loading state
                    searchButton.disabled = false;
                    loading.style.display = 'none';
                }
            }
            
            function displayResults(data, showImages) {
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
                    html += `
                        <table class="inventory-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Barcode</th>
                                    <th>Terex1</th>
                                    <th>Modelo</th>
                                    <th>Estilo</th>
                                    <th>Color</th>
                                    ${showImages ? '<th>Image</th>' : ''}
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    
                    data.inventory_items.forEach(item => {
                        html += `
                            <tr>
                                <td>${item.name || 'N/A'}</td>
                                <td>${item.barcode || 'N/A'}</td>
                                <td>${item.terex1}</td>
                                <td>${item.modelo}</td>
                                <td>${item.estilo || 'N/A'}</td>
                                <td>${item.color || 'N/A'}</td>
                        `;
                        
                        if (showImages) {
                            if (item.public_url) {
                                html += `<td><img src="${item.public_url}" alt="Item image" class="item-image"></td>`;
                            } else {
                                html += `<td>No image</td>`;
                            }
                        }
                        
                        html += `</tr>`;
                    });
                    
                    html += `
                            </tbody>
                        </table>
                    `;
                }
                
                results.innerHTML = html;
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
        return {"modelos": sorted(list(set(modelos)))}  # Remove duplicates and sort
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching modelos: {str(e)}")

@app.post("/search", response_model=SearchResult)
async def search_inventory(request: SearchRequest):
    """Search for inventory items by exact modelo match"""
    
    modelo = request.modelo.strip()
    if not modelo:
        raise HTTPException(status_code=400, detail="Modelo cannot be empty")
    
    # Get inventory items for the modelo
    inventory_records = supabase.table("inventario1").select("*").eq("modelo", modelo).gte("terex1", 1).execute()
    
    # Process inventory items and add images if requested
    processed_items = []
    for item in inventory_records.data:
        inventory_item = InventoryItem(
            name=item.get("name"),
            barcode=item.get("barcode"),
            terex1=item.get("terex1", 0),
            modelo=item.get("modelo", ""),
            estilo=item.get("estilo"),
            color=item.get("color"),
            estilo_id=item.get("estilo_id"),
            color_id=item.get("color_id")
        )
        
        # Get image if requested and IDs are available
        if request.con_imagenes and item.get("estilo_id") and item.get("color_id"):
            image_result = supabase.table("image_uploads").select("public_url").eq("estilo_id", item["estilo_id"]).eq("color_id", item["color_id"]).limit(1).execute()
            if image_result.data:
                inventory_item.public_url = image_result.data[0]["public_url"]
        
        processed_items.append(inventory_item)
    
    return SearchResult(
        modelo=modelo,
        inventory_items=processed_items,
        total_inventory_items=len(processed_items)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)