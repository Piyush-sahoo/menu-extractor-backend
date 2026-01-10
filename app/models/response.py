"""
Response models for Menu Extractor API.
Structured with veg/non-veg categorization, cuisines, and price variants.
"""
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel

class PriceInfo(BaseModel):
    """Price structure supporting half/full plate variants."""
    half: Union[float, str] = "NA"  # Number or "NA"
    full: Union[float, str] = "NA"  # Number or "NA"
    unit: str = "₹"

class MenuItem(BaseModel):
    """Individual menu item with detailed info."""
    name: str
    description: Optional[str] = None
    prices: PriceInfo = PriceInfo()
    cuisine: Optional[str] = None  # North Indian, Chinese, Italian, etc.
    spicy: bool = False
    bestseller: bool = False
    
class MenuCategory(BaseModel):
    """Category of menu items (starters, main_course, etc)."""
    name: str
    items: List[MenuItem] = []

class VegNonVegMenu(BaseModel):
    """Menu organized by veg/non-veg with categories underneath."""
    starters: List[MenuItem] = []
    main_course: List[MenuItem] = []
    seafood: List[MenuItem] = []
    rice_and_biryani: List[MenuItem] = []
    breads: List[MenuItem] = []
    desserts: List[MenuItem] = []
    beverages: List[MenuItem] = []

class StructuredMenu(BaseModel):
    """Complete menu structure with veg/non-veg at top level."""
    vegetarian: VegNonVegMenu = VegNonVegMenu()
    non_vegetarian: VegNonVegMenu = VegNonVegMenu()

class RestaurantInfo(BaseModel):
    """Restaurant details."""
    name: str
    address: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None

class MenuResponse(BaseModel):
    """Main API response model."""
    restaurant: RestaurantInfo
    menu: StructuredMenu = StructuredMenu()
    meta: Optional[Dict[str, Any]] = {}

# Legacy support
class LegacyMenuItem(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    price_text: Optional[str] = None
    currency: str = "INR"
    veg: bool = False
    category: Optional[str] = None
    confidence: float = 1.0
    source: str = "unknown"
    metadata: Optional[Dict[str, Any]] = {}

class LegacyMenuCategory(BaseModel):
    name: str
    items: List[LegacyMenuItem]
