from abc import ABC, abstractmethod

class StorageProvider(ABC):
    @abstractmethod
    async def save(self, source_path: str, dest_key: str) -> str:
        """Save file from source_path to storage. Returns the storage key."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> str:
        """Get the absolute path for a stored file."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a file from storage."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a file exists in storage."""
        pass
