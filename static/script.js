// Global Variables
let allModelos = [];
let selectedModeloIndex = -1;
let filteredModelos = [];
let itemQuantities = {};
let cartItemsCount = 0;
let carouselImages = [];
let currentImageIndex = 0;

// =============================================================================
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', function() {
    loadModelos();
    loadPopularStyles();
    loadCartItems();
    setupEventListeners();
});

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const dropdown = document.getElementById('autocompleteDropdown');
    
    // Search input event listeners
    searchInput.addEventListener('input', handleSearchInput);
    searchInput.addEventListener('keydown', handleSearchKeydown);
    
    // Click outside to close dropdown
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            hideDropdown();
        }
    });
    
    // Keyboard shortcuts for carousel
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeCarousel();
        } else if (e.key === 'ArrowLeft') {
            previousImage();
        } else if (e.key === 'ArrowRight') {
            nextImage();
        }
    });
    
    // Close modals when clicking outside
    setupModalCloseHandlers();
}

function setupModalCloseHandlers() {
    // Cart modal
    window.onclick = function(event) {
        const cartModal = document.getElementById('cartModal');
        if (event.target == cartModal) {
            cartModal.style.display = 'none';
        }
    }
    
    // Carousel modal
    document.getElementById('imageCarouselModal').onclick = function(event) {
        if (event.target === this) {
            closeCarousel();
        }
    }
}

// =============================================================================
// DATA LOADING FUNCTIONS
// =============================================================================

async function loadModelos() {
    try {
        const response = await fetch('/api/modelos');
        const data = await response.json();
        allModelos = data.modelos;
    } catch (error) {
        console.error('Error loading modelos:', error);
    }
}

async function loadPopularStyles() {
    try {
        const response = await fetch('/api/popular-styles');
        const data = await response.json();
        displayPopularStyles(data.popular_styles);
    } catch (error) {
        console.error('Error loading popular styles:', error);
        document.querySelector('.popular-styles-section').style.display = 'none';
    }
}

async function loadCartItems() {
    try {
        const response = await fetch('/api/cart');
        const data = await response.json();
        
        if (data.success) {
            displayCartItems(data.items);
            cartItemsCount = data.items.reduce((sum, item) => sum + item.qty, 0);
            updateCartCount();
        }
    } catch (error) {
        console.error('Error loading cart items:', error);
    }
}

// =============================================================================
// SEARCH FUNCTIONALITY
// =============================================================================

function handleSearchInput() {
    const query = this.value.trim();
    const popularStylesSection = document.querySelector('.popular-styles-section');
    
    if (query.length === 0) {
        hideDropdown();
        popularStylesSection.style.display = 'block';
        document.getElementById('results').innerHTML = '';
        return;
    }
    
    filteredModelos = allModelos.filter(modelo => 
        modelo.toLowerCase().includes(query.toLowerCase())
    );
    
    showDropdown(filteredModelos);
    selectedModeloIndex = -1;
}

function handleSearchKeydown(e) {
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
}

function showDropdown(modelos) {
    const dropdown = document.getElementById('autocompleteDropdown');
    
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
    const dropdown = document.getElementById('autocompleteDropdown');
    dropdown.style.display = 'none';
    selectedModeloIndex = -1;
}

function updateSelection() {
    const dropdown = document.getElementById('autocompleteDropdown');
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
    const searchInput = document.getElementById('searchInput');
    searchInput.value = modelo;
    hideDropdown();
    performSearch();
}

async function performSearch() {
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const popularStylesSection = document.querySelector('.popular-styles-section');
    
    const modelo = searchInput.value.trim();
    
    if (!modelo) {
        alert('Please select a modelo');
        return;
    }
    
    // Hide popular styles section during search
    popularStylesSection.style.display = 'none';
    
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
        window.currentSearchResults = data;
        
        // Log search activity
        logSearchActivity(modelo, data.total_inventory_items > 0, data.total_inventory_items);
        
    } catch (error) {
        results.innerHTML = `
            <div class="error">
                <strong>Error:</strong> ${error.message}
            </div>
        `;
        
        logSearchActivity(modelo, false, 0);
    } finally {
        searchButton.disabled = false;
        loading.style.display = 'none';
    }
}

function searchByStyle(estilo) {
    document.getElementById('searchInput').value = estilo;
    performStyleSearch(estilo);
}

async function performStyleSearch(estilo) {
    const searchButton = document.getElementById('searchButton');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const popularStylesSection = document.querySelector('.popular-styles-section');
    
    popularStylesSection.style.display = 'none';
    itemQuantities = {};
    
    searchButton.disabled = true;
    loading.style.display = 'block';
    results.innerHTML = '';
    
    try {
        const response = await fetch('/search-style', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                estilo: estilo
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Style search failed');
        }
        
        displayResults(data);
        window.currentSearchResults = data;
        
        logSearchActivity(estilo, data.total_inventory_items > 0, data.total_inventory_items);
        
    } catch (error) {
        results.innerHTML = `
            <div class="error">
                <strong>Error:</strong> ${error.message}
            </div>
        `;
        
        logSearchActivity(estilo, false, 0);
    } finally {
        searchButton.disabled = false;
        loading.style.display = 'none';
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
    }
}

// =============================================================================
// DISPLAY FUNCTIONS
// =============================================================================

function displayPopularStyles(styles) {
    const container = document.getElementById('popularStylesContainer');
    
    if (!styles || styles.length === 0) {
        document.querySelector('.popular-styles-section').style.display = 'none';
        return;
    }
    
    container.innerHTML = '';
    
    styles.forEach(style => {
        const styleElement = document.createElement('div');
        styleElement.className = 'style-item';
        styleElement.onclick = () => searchByStyle(style.estilo);
        styleElement.title = `${style.estilo} - ${style.total_qty} sold`;
        
        const imageHtml = style.public_url_webp ? 
            `<img src="${style.public_url_webp}" alt="${style.estilo}" class="style-image" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
             <div class="style-placeholder" style="display: none;">No Image</div>` :
            `<div class="style-placeholder">No Image</div>`;
        
        styleElement.innerHTML = imageHtml;
        container.appendChild(styleElement);
    });
}

function displayResults(data) {
    const results = document.getElementById('results');
    
    if (data.total_inventory_items === 0) {
        results.innerHTML = `
            <div class="no-results">
                <h3>No inventory items found</h3>
                <p>No items found for "${data.modelo || data.estilo}" with stock available</p>
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="match-info">
            <h3>✅ Found: ${data.modelo || data.estilo}</h3>
            <p><strong>Inventory Items Found:</strong> ${data.total_inventory_items}</p>
        </div>
    `;
    
    if (data.inventory_items.length > 0) {
        html += `<div class="inventory-container">`;
        
        data.inventory_items.forEach((item, index) => {
            const itemName = item.name || 'N/A';
            const itemId = `item_${index}`;
            const precio = item.precio ? `$${item.precio}` : 'N/A';
            
            if (!itemQuantities[itemId]) {
                itemQuantities[itemId] = 1;
            }
            
            html += `
                <div class="inventory-item">
                    <div class="item-image-container">
            `;
            
            if (item.public_url_webp && item.estilo_id && item.color_id) {
                const safeItemName = (itemName || 'Product').replace(/'/g, "\\'");
                html += `<img src="${item.public_url_webp}" alt="Item image" class="item-image" onclick="openImageCarousel(${item.estilo_id}, ${item.color_id}, '${safeItemName}')" title="Click to view all images">`;
            } else if (item.public_url_webp) {
                html += `<img src="${item.public_url_webp}" alt="Item image" class="item-image">`;
            } else {
                html += `<div class="item-image" style="background-color: #f0f0f0; display: flex; align-items: center; justify-content: center; color: #999; width: 120px; height: 120px; border-radius: 8px;">No image</div>`;
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
                            <span class="btn-text">ADD TO CART</span>
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += `</div>`;
    }
    
    results.innerHTML = html;
}

// =============================================================================
// CART FUNCTIONALITY
// =============================================================================

function updateCartCount() {
    const cartCount = document.getElementById('cartCount');
    
    if (cartItemsCount > 0) {
        cartCount.textContent = cartItemsCount;
        cartCount.classList.remove('hidden');
    } else {
        cartCount.classList.add('hidden');
    }
}

function toggleCartModal() {
    const cartModal = document.getElementById('cartModal');
    const isVisible = cartModal.style.display === 'flex';
    
    if (isVisible) {
        cartModal.style.display = 'none';
    } else {
        loadCartItems();
        cartModal.style.display = 'flex';
    }
}

function displayCartItems(cartItems) {
    const cartModalBody = document.getElementById('cartModalBody');
    const cartTotal = document.getElementById('cartTotal');
    
    if (!cartItems || cartItems.length === 0) {
        cartModalBody.innerHTML = '<div class="cart-empty">Your cart is empty</div>';
        cartTotal.innerHTML = '';
        return;
    }
    
    let html = '<div class="inventory-container">';
    let totalPrice = 0;
    
    cartItems.forEach((item, index) => {
        const itemName = item.name || 'N/A';
        const precio = item.precio || 0;
        const itemTotal = precio * item.qty;
        totalPrice += itemTotal;
        
        html += `
            <div class="inventory-item">
                <div class="item-image-container">
        `;
        
        if (item.public_url_webp) {
            html += `<img src="${item.public_url_webp}" alt="Item image" class="item-image" onclick="openImageCarousel(${item.estilo_id}, ${item.color_id}, '${itemName}')">`;
        } else {
            html += `<div class="item-image" style="background-color: #f0f0f0; display: flex; align-items: center; justify-content: center; color: #999; width: 120px; height: 120px; border-radius: 8px;">No image</div>`;
        }
        
        html += `
                </div>
                <div class="item-content">
                    <div class="item-name">${itemName}</div>
                    <div class="item-qty-price">
                        <div class="item-qty">Qty: ${item.qty}</div>
                        <div class="item-price">$${precio} each</div>
                        <div class="item-price">Total: $${itemTotal}</div>
                    </div>
                    <div class="cart-item-controls">
                        <div class="quantity-controls-inline">
                            <button class="qty-btn-inline" onclick="updateCartItemQuantity('${item.name}', ${item.qty - 1})">−</button>
                            <span class="qty-display-inline">${item.qty}</span>
                            <button class="qty-btn-inline" onclick="updateCartItemQuantity('${item.name}', ${item.qty + 1})">+</button>
                            <button class="qty-btn-inline" onclick="removeCartItem('${item.name}')" style="margin-left: 10px; color: #ff4444;">
                                <svg class="bin-icon" viewBox="0 0 24 24">
                                    <path d="M6 7H5V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1h-1V6a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1z"/>
                                    <path d="M19 7H5a1 1 0 0 0-1 1v11a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V8a1 1 0 0 0-1-1zM7 19a1 1 0 0 1-1-1V9h2v10H7zm4 0H9V9h2v10zm4 0h-2V9h2v10zm2-1a1 1 0 0 1-1 1V9h2v9z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    cartModalBody.innerHTML = html;
    cartTotal.innerHTML = `Total: $${totalPrice.toFixed(2)}`;
}

function addToCart(itemId, itemName, maxStock, imageUrl, precio) {
    const button = document.getElementById(`btn_${itemId}`);
    
    itemQuantities[itemId] = 1;
    button.classList.add('active');
    
    if (itemQuantities[itemId] === 1) {
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
    
    sendCartToDatabase(itemId, itemName, itemQuantities[itemId], precio, maxStock, imageUrl, 'add');
    
    cartItemsCount++;
    updateCartCount();
}

function removeFromCart(itemId) {
    const button = document.getElementById(`btn_${itemId}`);
    const itemName = getItemNameFromId(itemId);
    
    button.classList.remove('active');
    button.innerHTML = '<span class="btn-text">ADD TO CART</span>';
    
    sendCartToDatabase(itemId, itemName, 0, 0, 0, '', 'remove');
    
    delete itemQuantities[itemId];
    setTimeout(loadCartItems, 100);
}

function incrementQuantity(itemId, maxStock) {
    if (itemQuantities[itemId] < maxStock) {
        itemQuantities[itemId]++;
        updateButtonDisplay(itemId, maxStock);
        
        const itemName = getItemNameFromId(itemId);
        sendCartToDatabase(itemId, itemName, itemQuantities[itemId], 0, maxStock, '', 'update');
    }
}

function decrementQuantity(itemId, maxStock) {
    if (itemQuantities[itemId] > 1) {
        itemQuantities[itemId]--;
        updateButtonDisplay(itemId, maxStock);
        
        const itemName = getItemNameFromId(itemId);
        sendCartToDatabase(itemId, itemName, itemQuantities[itemId], 0, maxStock, '', 'update');
    }
}

function updateButtonDisplay(itemId, maxStock) {
    const button = document.getElementById(`btn_${itemId}`);
    const quantity = itemQuantities[itemId];
    
    if (quantity === 1) {
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
        button.innerHTML = `
            <div class="quantity-controls-inline">
                <button class="qty-btn-inline" onclick="event.stopPropagation(); decrementQuantity('${itemId}', ${maxStock})">−</button>
                <span class="qty-display-inline">${quantity}</span>
                <button class="qty-btn-inline" onclick="event.stopPropagation(); incrementQuantity('${itemId}', ${maxStock})" ${quantity >= maxStock ? 'disabled' : ''}>+</button>
            </div>
        `;
    }
}

function getItemNameFromId(itemId) {
    const itemIndex = itemId.replace('item_', '');
    const inventoryItems = window.currentSearchResults?.inventory_items || [];
    if (inventoryItems[itemIndex]) {
        return inventoryItems[itemIndex].name || 'Unknown Item';
    }
    return 'Unknown Item';
}

async function updateCartItemQuantity(itemName, newQty) {
    if (newQty <= 0) {
        removeCartItem(itemName);
        return;
    }
    
    try {
        const response = await fetch('/api/cart/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                item_name: itemName,
                new_qty: newQty
            })
        });
        
        const result = await response.json();
        if (result.success) {
            loadCartItems();
        }
    } catch (error) {
        console.error('Error updating cart item:', error);
    }
}

async function removeCartItem(itemName) {
    try {
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
        if (result.success) {
            loadCartItems();
        }
    } catch (error) {
        console.error('Error removing cart item:', error);
    }
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

// =============================================================================
// IMAGE CAROUSEL FUNCTIONALITY
// =============================================================================

async function openImageCarousel(estiloId, colorId, itemName) {
    const modal = document.getElementById('imageCarouselModal');
    const loading = document.getElementById('carouselLoading');
    const image = document.getElementById('carouselImage');
    const footer = document.getElementById('carouselFooter');
    const title = document.getElementById('carouselTitle');
    const prevBtn = document.getElementById('carouselPrev');
    const nextBtn = document.getElementById('carouselNext');
    
    modal.style.display = 'flex';
    loading.style.display = 'flex';
    loading.innerHTML = 'Loading images...';
    image.style.display = 'none';
    footer.style.display = 'none';
    prevBtn.style.display = 'none';
    nextBtn.style.display = 'none';
    
    title.textContent = itemName || 'Product Images';
    
    try {
        const response = await fetch(`/api/images/${estiloId}/${colorId}`);
        const data = await response.json();
        
        if (data.success && data.images && data.images.length > 0) {
            carouselImages = data.images;
            currentImageIndex = 0;
            
            loading.style.display = 'none';
            showCarouselImage();
            
            if (carouselImages.length > 1) {
                footer.style.display = 'flex';
                prevBtn.style.display = 'flex';
                nextBtn.style.display = 'flex';
                updateCarouselNavigation();
                createThumbnails();
            }
        } else {
            loading.innerHTML = 'No additional images available';
            setTimeout(() => {
                closeCarousel();
            }, 2000);
        }
    } catch (error) {
        console.error('Error loading carousel images:', error);
        loading.innerHTML = 'Error loading images';
        setTimeout(() => {
            closeCarousel();
        }, 2000);
    }
}

function showCarouselImage() {
    const image = document.getElementById('carouselImage');
    const counter = document.getElementById('carouselCounter');
    
    if (carouselImages.length > 0) {
        image.src = carouselImages[currentImageIndex].public_url_webp;
        image.style.display = 'block';
        counter.textContent = `${currentImageIndex + 1} / ${carouselImages.length}`;
        updateThumbnailsActive();
    }
}

function updateCarouselNavigation() {
    const prevBtn = document.getElementById('carouselPrev');
    const nextBtn = document.getElementById('carouselNext');
    
    prevBtn.disabled = currentImageIndex === 0;
    nextBtn.disabled = currentImageIndex === carouselImages.length - 1;
}

function createThumbnails() {
    const thumbnailsContainer = document.getElementById('carouselThumbnails');
    thumbnailsContainer.innerHTML = '';
    
    carouselImages.forEach((img, index) => {
        const thumbnail = document.createElement('img');
        thumbnail.src = img.public_url_webp;
        thumbnail.className = 'carousel-thumbnail';
        thumbnail.onclick = () => goToImage(index);
        thumbnailsContainer.appendChild(thumbnail);
    });
    
    updateThumbnailsActive();
}

function updateThumbnailsActive() {
    const thumbnails = document.querySelectorAll('.carousel-thumbnail');
    thumbnails.forEach((thumb, index) => {
        if (index === currentImageIndex) {
            thumb.classList.add('active');
        } else {
            thumb.classList.remove('active');
        }
    });
}

function previousImage() {
    if (currentImageIndex > 0) {
        currentImageIndex--;
        showCarouselImage();
        updateCarouselNavigation();
    }
}

function nextImage() {
    if (currentImageIndex < carouselImages.length - 1) {
        currentImageIndex++;
        showCarouselImage();
        updateCarouselNavigation();
    }
}

function goToImage(index) {
    currentImageIndex = index;
    showCarouselImage();
    updateCarouselNavigation();
}

function closeCarousel() {
    const modal = document.getElementById('imageCarouselModal');
    modal.style.display = 'none';
    carouselImages = [];
    currentImageIndex = 0;
}