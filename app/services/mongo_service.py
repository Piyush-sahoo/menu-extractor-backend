"""
MongoDB Service for Menu Storage.
Stores menu data with 30-day TTL (auto-expires after 30 days).
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

logger = logging.getLogger(__name__)

class MongoService:
    """
    MongoDB service for persistent menu storage.
    Documents auto-expire after 30 days.
    """
    
    def __init__(self):
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client.menu_extractor
        self.menus = self.db.menus
        
    async def setup_indexes(self):
        """Create TTL index for auto-expiration after 30 days."""
        try:
            # TTL index on created_at field - expires after 30 days
            await self.menus.create_index(
                "created_at",
                expireAfterSeconds=30 * 24 * 60 * 60  # 30 days in seconds
            )
            # Index on restaurant name for fast lookups
            await self.menus.create_index("restaurant_name")
            logger.info("MongoDB indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create MongoDB indexes: {e}")
    
    async def save_menu(
        self,
        restaurant_name: str,
        location: str,
        restaurant_info: Dict[str, Any],
        menu: Dict[str, Any],
        meta: Dict[str, Any]
    ) -> str:
        """
        Save menu to MongoDB.
        Returns the document ID.
        """
        document = {
            "restaurant_name": restaurant_name,
            "location": location,
            "restaurant_info": restaurant_info,
            "menu": menu,
            "meta": meta,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30)
        }
        
        # Upsert - update if exists, insert if not
        result = await self.menus.update_one(
            {"restaurant_name": restaurant_name, "location": location},
            {"$set": document},
            upsert=True
        )
        
        logger.info(f"Saved menu for {restaurant_name} to MongoDB")
        return str(result.upserted_id) if result.upserted_id else "updated"
    
    async def get_menu(
        self,
        restaurant_name: Optional[str] = None,
        location: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Get menu from MongoDB.
        Returns None if not found or expired.
        """
        if not restaurant_name:
            # If no name provided (e.g. URL only), we can't search by name
            # We could potentially search by google_maps_url if we stored it, 
            # but for now just return None to trigger fresh extraction
            return None
            
        query = {"restaurant_name": {"$regex": restaurant_name, "$options": "i"}}
        if location:
            query["location"] = {"$regex": location, "$options": "i"}
        
        document = await self.menus.find_one(query)
        
        if document:
            # Convert ObjectId to string for JSON serialization
            document["_id"] = str(document["_id"])
            logger.info(f"Found menu for {restaurant_name} in MongoDB")
            return document
        
        return None
        
        return None
    
    async def get_all_menus(
        self,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all stored menus with pagination."""
        cursor = self.menus.find().sort("created_at", -1).skip(skip).limit(limit)
        menus = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            menus.append(doc)
        return menus
    
    async def get_menu_count(self) -> int:
        """Get total count of stored menus."""
        return await self.menus.count_documents({})
    
    async def delete_menu(self, restaurant_name: str, location: str = "") -> bool:
        """Delete a menu from MongoDB."""
        query = {"restaurant_name": restaurant_name}
        if location:
            query["location"] = location
        
        result = await self.menus.delete_one(query)
        return result.deleted_count > 0
    
    async def close(self):
        """Close MongoDB connection."""
        self.client.close()
